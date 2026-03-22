"""LangGraph definition for the email ingestion pipeline."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from ingest_email_engine.state import TicketState
from ingest_email_engine.nodes.assign_agent import assign_agent
from ingest_email_engine.nodes.categorize import categorize
from ingest_email_engine.nodes.draft_response import draft_response
from ingest_email_engine.nodes.enrich_db import enrich_db
from ingest_email_engine.nodes.enrich_sentry import enrich_sentry
from ingest_email_engine.nodes.ingest_clean import ingest_clean


Route = Literal["enrich_sentry", "enrich_db", "draft_response"]


def route_after_categorize(state: TicketState) -> Route:
    """Route based on the inferred category."""

    category = state.get("category")
    if category == "bug":
        return "enrich_sentry"
    if category == "refund":
        return "enrich_db"
    return "draft_response"


def build_graph() -> StateGraph[TicketState]:
    """Build the ingest email pipeline graph."""

    graph: StateGraph[TicketState] = StateGraph(TicketState)

    graph.add_node("ingest_clean", ingest_clean)
    graph.add_node("categorize", categorize)
    graph.add_node("enrich_sentry", enrich_sentry)
    graph.add_node("enrich_db", enrich_db)
    graph.add_node("draft_response", draft_response)
    graph.add_node("assign_agent", assign_agent)

    graph.add_edge(START, "ingest_clean")
    graph.add_edge("ingest_clean", "categorize")

    graph.add_conditional_edges(
        "categorize",
        route_after_categorize,
        {
            "enrich_sentry": "enrich_sentry",
            "enrich_db": "enrich_db",
            "draft_response": "draft_response",
        },
    )

    graph.add_edge("enrich_sentry", "draft_response")
    graph.add_edge("enrich_db", "draft_response")

    graph.add_edge("draft_response", "assign_agent")
    graph.add_edge("assign_agent", END)

    return graph


email_processing_app = build_graph().compile()
