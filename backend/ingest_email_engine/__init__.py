"""Email ingestion engine powered by LangGraph.

This package contains a small, best-practice scaffold for a ticket ingestion
pipeline. The entrypoint is `email_processing_app` in `graph.py`.
"""

from .graph import email_processing_app

__all__ = ["email_processing_app"]
