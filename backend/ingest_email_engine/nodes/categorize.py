"""Node: categorize the ticket using the LLM with structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ingest_email_engine.llm import get_llm
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


def categorize(state: TicketState) -> dict[str, object]:
    """Analyze the email and return category + priority.

    Enforces structured output using a Pydantic schema.
    """

    logger = get_logger(__name__)
    logger.info("node=categorize start")

    llm = get_llm()
    structured_llm = llm.with_structured_output(_Categorization)

    email_body = state["email_body"]
    customer_email = state["customer_email"]

    prompt = (
        "You are a customer support triage assistant. "
        "Given the customer's email, classify it into a category and priority.\n\n"
        "Allowed categories: bug, refund, info.\n"
        "Allowed priorities: high, low.\n\n"
        f"Customer email: {customer_email}\n"
        f"Email body:\n{email_body}\n"
    )

    result: _Categorization = structured_llm.invoke(prompt)

    logger.info("node=categorize done category=%s priority=%s", result.category, result.priority)
    return {"category": result.category, "priority": result.priority}
