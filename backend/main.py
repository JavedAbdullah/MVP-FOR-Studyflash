"""FastAPI server for the customer support ticketing MVP.

Features:
  - PostgreSQL persistence via SQLAlchemy
  - LangGraph ingestion pipeline invoked by a background poller
  - Read-only ticket endpoints for the Next.js dashboard
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from database import Agent, Message, MockCustomer, SessionLocal, Ticket, get_db, init_db
from ingest_email_engine.graph import email_processing_app


app = FastAPI(title="Support Ticketing MVP API")

SIMULATION_INTERVAL_S: int = int(os.getenv("SIMULATION_INTERVAL_S", "15"))

logger = logging.getLogger("support_mvp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentOut(BaseModel):
    """Agent API representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str


class MessageOut(BaseModel):
    """Message API representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    sender_type: str
    body: str
    outlook_message_id: str | None
    created_at: datetime


class TicketOut(BaseModel):
    """Ticket API representation (includes agent + messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    customer_email: str
    status: str
    category: str | None
    priority: str | None
    ai_draft: str | None
    agent: AgentOut | None
    messages: list[MessageOut]
    created_at: datetime


class ReplyIn(BaseModel):
    body: str


DEFAULT_MOCK_EMAILS: list[dict[str, str]] = [
    {
        "subject": "App crashes on login",
        "body": "Every time I try to open my flashcards, the app closes. I am using an iPhone 13.",
        "sender": "angry_user@gmail.com",
        "message_id": "<mock-id-12345>",
    },
    {
        "subject": "Refund please",
        "body": "I forgot to cancel my trial, can I get my money back?",
        "sender": "distracted_student@yahoo.com",
        "message_id": "<mock-id-67890>",
    },
    {
        "subject": "How to share decks?",
        "body": "Hi, how can I send my study deck to my classmate?",
        "sender": "curious_guy@hotmail.com",
        "message_id": "<mock-id-abcde>",
    },
    {
        "subject": "Billing question",
        "body": "Can you explain what my next charge will be and when?",
        "sender": "billing_question@outlook.com",
        "message_id": "<mock-id-fghij>",
    },
]


def _build_subject_from_tags(tags: set[str], body: str) -> str:
    if "refund-request" in tags or "refund" in tags:
        return "Refund request"
    if "subscription-cancellation" in tags or "cancellation" in tags:
        return "Cancel subscription"
    if "bug" in tags or "bug-report" in tags:
        return "Bug report"

    first_line = (body or "").strip().splitlines()[0] if (body or "").strip() else "Support request"
    return first_line[:80]


def _load_sample_emails_from_tickets_dir(tickets_dir: Path) -> list[dict[str, str]]:
    """Load anonymized support request samples from txt files.

    Expected format:
      Tags: a, b, c

      ---
      <body>
    """

    if not tickets_dir.exists() or not tickets_dir.is_dir():
        return []

    emails: list[dict[str, str]] = []

    for path in sorted(tickets_dir.glob("ticket_*.txt")):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        raw = raw.replace("\r\n", "\n")
        lines = raw.split("\n")
        tags: set[str] = set()

        if lines and lines[0].lower().startswith("tags:"):
            tags = {t.strip() for t in lines[0][5:].split(",") if t.strip()}

        # Everything after the first '---' is treated as the body
        body = raw
        if "---" in raw:
            body = raw.split("---", 1)[1]
        body = body.strip()

        if not body:
            continue

        # Skip clearly non-actionable samples
        if "garbage" in tags:
            continue

        stem = path.stem  # e.g. ticket_3528
        sender = f"{stem}@example.com"
        body = body.replace("[EMAIL]", sender)
        subject = _build_subject_from_tags(tags, body)

        emails.append(
            {
                "subject": subject,
                "body": body,
                "sender": sender,
                "message_id": f"<{stem}>",
            }
        )

    return emails


def _get_simulation_emails() -> list[dict[str, str]]:
    emails = getattr(app.state, "simulation_emails", None)
    if isinstance(emails, list) and emails:
        return emails
    return DEFAULT_MOCK_EMAILS


def _seed_data(db: Session, *, emails: list[dict[str, str]]) -> None:
    """Seed minimal agents/customers if tables are empty."""

    existing_agent = db.execute(select(Agent).limit(1)).scalar_one_or_none()
    if not existing_agent:
        db.add_all(
            [
                Agent(name="Alice", email="alice@support.local", role="support"),
                Agent(name="Bob", email="bob@support.local", role="billing"),
                Agent(name="Cleo", email="cleo@support.local", role="general"),
            ]
        )

    for email in {e["sender"] for e in emails}:
        customer = db.execute(
            select(MockCustomer).where(MockCustomer.email == email)
        ).scalar_one_or_none()
        if not customer:
            db.add(MockCustomer(email=email, subscription_plan="pro"))

    db.commit()


def _persist_ticket_from_email(
    db: Session, email: dict[str, str], final_state: dict[str, Any]
) -> Ticket:
    """Create Ticket + first Message from pipeline state."""

    sender = email["sender"]
    subject = email["subject"]
    body = email["body"]
    message_id = email.get("message_id")

    customer = db.execute(
        select(MockCustomer).where(MockCustomer.email == sender)
    ).scalar_one_or_none()
    if not customer:
        customer = MockCustomer(email=sender, subscription_plan="free")
        db.add(customer)
        db.flush()

    ticket = Ticket(
        subject=subject,
        customer_email=sender,
        status="open",
        category=final_state.get("category"),
        priority=final_state.get("priority"),
        ai_draft=final_state.get("draft_response"),
        agent_id=final_state.get("suggested_agent_id"),
    )
    db.add(ticket)
    db.flush()

    db.add(
        Message(
            ticket_id=ticket.id,
            sender_type="customer",
            body=body,
            outlook_message_id=message_id,
        )
    )

    db.commit()
    db.refresh(ticket)
    return ticket


def send_smtp_reply(to_email: str, body: str, in_reply_to_id: str | None) -> None:
    """Mock SMTP sender that shows how to keep Outlook threading parity.

    Uses `In-Reply-To` and `References` headers.
    The actual send is disabled (wrapped in `if False:`) for MVP safety.
    """

    smtp_host = os.getenv("SMTP_HOST", "smtp.example.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "support@example.com")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = "Re: Your support request"

    if in_reply_to_id:
        msg["In-Reply-To"] = in_reply_to_id
        msg["References"] = in_reply_to_id

    msg.set_content(body)

    # Exact boilerplate for SMTP sending (disabled for MVP).
    if False:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        logger.info("SMTP reply sent to=%s in_reply_to=%s", to_email, in_reply_to_id)

    logger.info(
        "Mock SMTP reply prepared to=%s in_reply_to=%s (sending disabled)",
        to_email,
        in_reply_to_id,
    )


async def mock_email_poller() -> None:
    """Background task that simulates a mailbox poll every 15 seconds."""

    try:
        while True:
            await asyncio.sleep(SIMULATION_INTERVAL_S)
            email = random.choice(_get_simulation_emails())

            initial_state = {
                "subject": email["subject"],
                "email_body": email["body"],
                "customer_email": email["sender"],
            }

            try:
                final_state: dict[str, Any] = await asyncio.to_thread(
                    email_processing_app.invoke, initial_state
                )
            except Exception:
                logger.exception("LangGraph pipeline failed")
                continue

            def _save() -> None:
                # Use the same session factory as the API. This runs in a worker thread.
                db = SessionLocal()
                try:
                    _persist_ticket_from_email(db, email, final_state)
                finally:
                    db.close()

            try:
                await asyncio.to_thread(_save)
            except Exception:
                logger.exception("Failed to persist ticket")
                continue

            # Schedule the next tick for status UI countdown.
            app.state.poller_next_tick_at = datetime.now(timezone.utc) + timedelta(
                seconds=SIMULATION_INTERVAL_S
            )
    except asyncio.CancelledError:
        logger.info("Mock email poller cancelled")
        raise


def _poller_running() -> bool:
    task = getattr(app.state, "poller_task", None)
    return bool(task and not task.done())


def _seconds_until_next_tick() -> int | None:
    if not _poller_running():
        return None

    next_tick_at = getattr(app.state, "poller_next_tick_at", None)
    if not isinstance(next_tick_at, datetime):
        return SIMULATION_INTERVAL_S

    now = datetime.now(timezone.utc)
    if next_tick_at.tzinfo is None:
        next_tick_at = next_tick_at.replace(tzinfo=timezone.utc)
    remaining = int((next_tick_at - now).total_seconds())
    return max(0, remaining)


def _start_poller() -> None:
    if _poller_running():
        return
    app.state.poller_next_tick_at = datetime.now(timezone.utc) + timedelta(
        seconds=SIMULATION_INTERVAL_S
    )
    app.state.poller_task = asyncio.create_task(mock_email_poller())


def _stop_poller() -> None:
    task = getattr(app.state, "poller_task", None)
    if task and not task.done():
        task.cancel()
    app.state.poller_task = None
    app.state.poller_next_tick_at = None


@app.on_event("startup")
async def on_startup() -> None:
    init_db()

    # Prefer samples from the workspace `tickets/` folder (bind-mounted in docker-compose).
    tickets_dir = Path(os.getenv("SAMPLE_TICKETS_DIR", "/app/tickets"))
    samples = _load_sample_emails_from_tickets_dir(tickets_dir)
    app.state.simulation_emails = samples

    db = SessionLocal()
    try:
        _seed_data(db, emails=_get_simulation_emails())
    finally:
        db.close()

    app.state.poller_task = None
    app.state.poller_next_tick_at = None


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _stop_poller()


@app.get("/simulation/status")
async def simulation_status() -> dict[str, object]:
    return {
        "running": _poller_running(),
        "interval_s": SIMULATION_INTERVAL_S,
        "next_in_s": _seconds_until_next_tick(),
    }


@app.post("/simulation/start")
async def simulation_start() -> dict[str, object]:
    _start_poller()
    return {
        "running": _poller_running(),
        "interval_s": SIMULATION_INTERVAL_S,
        "next_in_s": _seconds_until_next_tick(),
    }


@app.post("/simulation/stop")
async def simulation_stop() -> dict[str, object]:
    _stop_poller()
    return {
        "running": _poller_running(),
        "interval_s": SIMULATION_INTERVAL_S,
        "next_in_s": _seconds_until_next_tick(),
    }


@app.post("/simulation/toggle")
async def simulation_toggle() -> dict[str, bool]:
    if _poller_running():
        _stop_poller()
        return {"running": False}
    _start_poller()
    return {"running": True}


@app.post("/admin/clear")
def admin_clear(db: Session = Depends(get_db)) -> dict[str, int | bool]:
    """MVP-only endpoint to delete all tickets (and their messages).

    Also stops the inbox simulation so it doesn't recreate tickets while clearing.
    """

    _stop_poller()

    deleted_messages = db.execute(delete(Message)).rowcount or 0
    deleted_tickets = db.execute(delete(Ticket)).rowcount or 0
    db.commit()

    return {
        "running": _poller_running(),
        "deleted_tickets": int(deleted_tickets),
        "deleted_messages": int(deleted_messages),
    }


@app.get("/tickets", response_model=list[TicketOut])
def list_tickets(db: Session = Depends(get_db)) -> list[Ticket]:
    tickets = (
        db.query(Ticket)
        .options(joinedload(Ticket.messages), joinedload(Ticket.agent))
        .order_by(Ticket.created_at.desc())
        .all()
    )

    for t in tickets:
        t.messages.sort(key=lambda m: m.created_at)
    return tickets


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.messages), joinedload(Ticket.agent))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.messages.sort(key=lambda m: m.created_at)
    return ticket


@app.post("/tickets/{ticket_id}/reply", response_model=TicketOut)
def reply_to_ticket(
    ticket_id: int, payload: ReplyIn, db: Session = Depends(get_db)
) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.messages), joinedload(Ticket.agent))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.messages.sort(key=lambda m: m.created_at)
    first_msg = ticket.messages[0] if ticket.messages else None
    in_reply_to_id = first_msg.outlook_message_id if first_msg else None

    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Body is required")

    db.add(
        Message(
            ticket_id=ticket.id,
            sender_type="agent",
            body=body,
            outlook_message_id=None,
        )
    )

    # Keep ticket open (or pending). For MVP we keep it as-is.
    db.commit()

    send_smtp_reply(ticket.customer_email, body, in_reply_to_id)

    db.refresh(ticket)
    ticket.messages.sort(key=lambda m: m.created_at)
    return ticket


@app.post("/tickets/{ticket_id}/close", response_model=TicketOut)
def close_ticket(ticket_id: int, db: Session = Depends(get_db)) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.messages), joinedload(Ticket.agent))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = "closed"
    db.commit()
    db.refresh(ticket)
    ticket.messages.sort(key=lambda m: m.created_at)
    return ticket


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}