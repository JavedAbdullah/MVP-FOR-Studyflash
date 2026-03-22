"""FastAPI server for the customer support ticketing MVP.

Features:
  - PostgreSQL persistence via SQLAlchemy
  - LangGraph ingestion pipeline invoked by a background poller
  - Read-only ticket endpoints for the Next.js dashboard
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database import Agent, Message, MockCustomer, SessionLocal, Ticket, get_db, init_db
from ingest_email_engine.graph import email_processing_app


app = FastAPI(title="Support Ticketing MVP API")

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


MOCK_EMAILS: list[dict[str, str]] = [
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


def _seed_data(db: Session) -> None:
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

    for email in {e["sender"] for e in MOCK_EMAILS}:
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


async def mock_email_poller() -> None:
    """Background task that simulates a mailbox poll every 15 seconds."""

    while True:
        await asyncio.sleep(15)
        email = random.choice(MOCK_EMAILS)

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


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        _seed_data(db)
    finally:
        db.close()

    app.state.poller_task = asyncio.create_task(mock_email_poller())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    task = getattr(app.state, "poller_task", None)
    if task:
        task.cancel()


@app.get("/tickets", response_model=list[TicketOut])
def list_tickets(db: Session = Depends(get_db)) -> list[Ticket]:
    tickets = (
        db.query(Ticket)
        .options(joinedload(Ticket.messages), joinedload(Ticket.agent))
        .order_by(Ticket.created_at.desc())
        .all()
    )
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
    return ticket


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}