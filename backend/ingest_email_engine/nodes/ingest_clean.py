"""Node: ingest and clean raw email content (mock)."""

from __future__ import annotations

from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


def ingest_clean(state: TicketState) -> dict[str, object]:
    """Mock cleaning step for raw email content."""

    logger = get_logger(__name__)
    logger.info("node=ingest_clean start")

    cleaned = " ".join(state["email_body"].strip().split())

    logger.info("node=ingest_clean done")
    return {"email_body": cleaned}
