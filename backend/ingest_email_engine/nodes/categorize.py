"""Node: categorize the ticket using the LLM with structured output."""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
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

    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    text = getattr(response, "content", str(response))

    try:
        result = parser.parse(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        result = _Categorization.model_validate(json.loads(match.group(0)))

    logger.info("node=categorize done category=%s priority=%s", result.category, result.priority)
    return {"category": result.category, "priority": result.priority}
