"""LLM initialization for the ingest pipeline.

Uses a local Ollama instance via LangChain `ChatOllama`.

Environment variables:
    - OLLAMA_BASE_URL: defaults to `http://localhost:11434`
    - OLLAMA_MODEL: defaults to `llama3`
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Final

from langchain_community.chat_models import ChatOllama


DEFAULT_MODEL: Final[str] = os.getenv("OLLAMA_MODEL", "llama3")
DEFAULT_BASE_URL: Final[str] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


__all__ = ["DEFAULT_MODEL", "DEFAULT_BASE_URL", "get_llm", "llm"]


@lru_cache(maxsize=1)
def get_llm(model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL) -> ChatOllama:
    """Create (and cache) a ChatOllama client."""

    return ChatOllama(model=model, base_url=base_url, temperature=0)


# Module-level instance export.
# Note: does not verify Ollama availability at import-time.
llm: ChatOllama = get_llm()
