"""Node: draft a customer support response using the LLM."""

from __future__ import annotations

from ingest_email_engine.llm import get_llm
from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


def draft_response(state: TicketState) -> dict[str, object]:
    """Generate a draft response email to the customer."""

    logger = get_logger(__name__)
    logger.info("node=draft_response start")

    llm = get_llm()

    email_body = state["email_body"]
    customer_email = state["customer_email"]
    enriched_context = state.get("enriched_context") or "(no additional context)"
    category = state.get("category") or "unknown"
    priority = state.get("priority") or "unknown"

    prompt = (
        "You are a helpful customer support agent. "
        "Write a concise, polite email reply. "
        "Do not mention internal tools (Sentry/DB). "
        "If you need more info, ask 1-2 clarifying questions.\n\n"
        f"Customer email: {customer_email}\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n\n"
        "Customer message:\n"
        f"{email_body}\n\n"
        "Internal context (may be empty):\n"
        f"{enriched_context}\n\n"
        "Return only the email body (no subject)."
    )

    response = llm.invoke(prompt)
    draft_text = getattr(response, "content", str(response))

    logger.info("node=draft_response done")
    return {"draft_response": draft_text}
