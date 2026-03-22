"""Node: enrich context from database (mock)."""

from __future__ import annotations

from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


def enrich_db(state: TicketState) -> dict[str, object]:
    """Return a mock string simulating a DB query for subscription status."""

    logger = get_logger(__name__)
    logger.info("node=enrich_db start")

    customer_email = state["customer_email"]
    context = (
        "[DB] Mock subscription lookup\n"
        f"- customer_email: {customer_email}\n"
        "- plan: pro\n"
        "- status: active\n"
        "- renewal_date: 2026-04-15\n"
    )

    logger.info("node=enrich_db done")
    return {"enriched_context": context}
