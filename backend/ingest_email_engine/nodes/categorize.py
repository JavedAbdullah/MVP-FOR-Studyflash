"""Node: categorize the ticket using the LLM with structured output."""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from ingest_email_engine.llm import anthropic_chat
from ingest_email_engine.logger import get_logger
from ingest_email_engine.state import TicketState


__all__ = ["categorize"]


class _Categorization(BaseModel):
    """Structured categorization output."""

    category: Literal["bug", "refund", "info"] = Field(
        ..., description="Ticket category derived from the email."
    )
    priority: Literal["high", "low"] = Field(
        ..., description="Ticket priority derived from urgency/severity."
    )


def _fallback_categorize(email_body: str) -> _Categorization:
    text = (email_body or "").lower()

    refund_keywords = [
        "refund",
        "chargeback",
        "billing",
        "charged",
        "charge",
        "payment",
        "invoice",
        "subscription",
        "cancel",
    ]
    bug_keywords = [
        "bug",
        "error",
        "crash",
        "issue",
        "broken",
        "doesn't work",
        "does not work",
        "fail",
        "failed",
        "unable",
        "can't",
        "cannot",
    ]

    if any(k in text for k in refund_keywords):
        category: Literal["bug", "refund", "info"] = "refund"
    elif any(k in text for k in bug_keywords):
        category = "bug"
    else:
        category = "info"

    high_keywords = ["urgent", "asap", "immediately", "critical", "blocked", "down", "outage"]
    priority: Literal["high", "low"] = "high" if any(k in text for k in high_keywords) else "low"

    return _Categorization(category=category, priority=priority)


def categorize(state: TicketState) -> dict[str, object]:
    """Analyze the email and return category + priority.

    Enforces structured output using a Pydantic schema.
    """

    logger = get_logger(__name__)
    logger.info("node=categorize start")

    parser = PydanticOutputParser(pydantic_object=_Categorization)

    email_body = state["email_body"]
    customer_email = state["customer_email"]

    system = (
        "You are a customer support triage assistant. "
        "Classify the email into category and priority. "
        "Return ONLY valid JSON that matches the schema."
    )

    human = (
        "Allowed categories: bug, refund, info.\n"
        "Allowed priorities: high, low.\n\n"
        f"Customer email: {customer_email}\n"
        f"Email body:\n{email_body}\n\n"
        f"{parser.get_format_instructions()}"
    )

    try:
        text = anthropic_chat(system=system, user=human, max_tokens=128)

        try:
            result = parser.parse(text)
        except Exception:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            result = _Categorization.model_validate(json.loads(match.group(0)))
    except Exception as exc:
        # Fail-open so the rest of the pipeline can continue and tickets can be created.
        logger.warning("LLM categorization failed; using fallback categorization: %s", exc)
        result = _fallback_categorize(email_body)

    logger.info("node=categorize done category=%s priority=%s", result.category, result.priority)
    return {"category": result.category, "priority": result.priority}
