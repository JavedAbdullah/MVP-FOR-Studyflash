"""LLM initialization for the ingest pipeline.

This module provides both a cached constructor (`get_llm`) and a best-effort
module-level export (`llm`).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Final

from langchain_openai import ChatOpenAI


DEFAULT_MODEL: Final[str] = "gpt-4o-mini"


__all__ = ["DEFAULT_MODEL", "get_llm", "llm"]


@lru_cache(maxsize=1)
def get_llm(model: str = DEFAULT_MODEL) -> ChatOpenAI:
    """Create (and cache) a ChatOpenAI client.

    Raises:
        RuntimeError: if `OPENAI_API_KEY` is not set.
    """

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        message = (
            "Missing OPENAI_API_KEY. Set it in backend/.env (or your environment) "
            "before running the ingest_email_engine pipeline."
        )
        raise RuntimeError(message)

    # ChatOpenAI reads OPENAI_API_KEY from the environment.
    return ChatOpenAI(model=model, temperature=0)


# Best-effort module-level instance export.
try:
    llm: ChatOpenAI | None = get_llm()
except RuntimeError:
    llm = None
