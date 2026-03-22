"""Node: draft a customer support response using the LLM."""

from __future__ import annotations

from ingest_email_engine.llm import anthropic_chat
from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


def draft_response(state: TicketState) -> dict[str, object]:
    """Generate a draft response email to the customer."""

    logger = get_logger(__name__)
    logger.info("node=draft_response start")

    email_body = state["email_body"]
    customer_email = state["customer_email"]
    enriched_context = state.get("enriched_context") or "(no additional context)"
    category = state.get("category") or "unknown"
    priority = state.get("priority") or "unknown"

    system = (
        "You are a helpful customer support agent. "
        "Write a concise, polite email reply. "
        "Do not mention internal tools (Sentry/DB). "
        "If you need more info, ask 1-2 clarifying questions."
    )

    user = (
        f"Customer email: {customer_email}\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n\n"
        "Customer message:\n"
        f"{email_body}\n\n"
        "Internal context (may be empty):\n"
        f"{enriched_context}\n\n"
        "Return only the email body (no subject)."
    )

    try:
        draft_text = anthropic_chat(system=system, user=user, max_tokens=300)
    except Exception as exc:
        logger.warning("LLM draft failed; using fallback draft: %s", exc)

        if category == "refund":
            draft_text = (
                "Hi there,\n\n"
                "Thanks for reaching out. I can help with a refund request. "
                "Could you share your order/invoice ID and the date you were charged?\n\n"
                "Once I have that, I’ll check the payment and confirm the next steps.\n\n"
                "Best regards,\nSupport"
            )
        elif category == "bug":
            draft_text = (
                "Hi there,\n\n"
                "Thanks for reporting this issue — I’m sorry for the trouble. "
                "Could you confirm the steps to reproduce, what you expected to happen, "
                "and any error message you’re seeing?\n\n"
                "If possible, also share your app version and OS/browser.\n\n"
                "Best regards,\nSupport"
            )
        else:
            draft_text = (
                "Hi there,\n\n"
                "Thanks for contacting support. I’m happy to help. "
                "Could you share a bit more detail about what you’re trying to do and what you see on your side?\n\n"
                "Best regards,\nSupport"
            )

    logger.info("node=draft_response done")
    return {"draft_response": draft_text}
