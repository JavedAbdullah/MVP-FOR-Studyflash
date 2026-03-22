"""Node: enrich context from Sentry (mock)."""

from __future__ import annotations

from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


def enrich_sentry(state: TicketState) -> dict[str, object]:
    """Return a mock string simulating Sentry error logs."""

    logger = get_logger(__name__)
    logger.info("node=enrich_sentry start")

    email_body = state["email_body"]
    context = (
        "[Sentry] Mock error logs\n"
        "- error: NullPointerException in checkout flow\n"
        "- last_seen: 2026-03-22T10:12:33Z\n"
        f"- email_snippet: {email_body[:120]}\n"
    )

    logger.info("node=enrich_sentry done")
    return {"enriched_context": context}
