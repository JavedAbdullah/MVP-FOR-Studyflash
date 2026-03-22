"""State definitions for the ingest email LangGraph pipeline."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class TicketState(TypedDict):
    """State carried through the email ingestion graph."""

    email_body: str
    customer_email: str

    category: NotRequired[str]
    priority: NotRequired[str]
    enriched_context: NotRequired[str]
    suggested_agent_id: NotRequired[int]
    draft_response: NotRequired[str]
