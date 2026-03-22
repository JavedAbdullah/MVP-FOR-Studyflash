"""Node: assign a support agent (simple rules)."""

from __future__ import annotations

from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


def assign_agent(state: TicketState) -> dict[str, object]:
    """Assign an agent id using simple, deterministic logic."""

    logger = get_logger(__name__)
    logger.info("node=assign_agent start")

    category = state.get("category")

    if category == "bug":
        agent_id = 1
    elif category == "refund":
        agent_id = 2
    else:
        agent_id = 3

    logger.info("node=assign_agent done agent_id=%s", agent_id)
    return {"suggested_agent_id": agent_id}
