"""LLM initialization for the ingest pipeline.

Uses Anthropic's Messages API. This keeps the ingestion pipeline simple and
does not require a local model runtime.

Environment variables:
    - ANTHROPIC_API_KEY: required
    - ANTHROPIC_MODEL: defaults to `claude-3-haiku-20240307`
    - ANTHROPIC_TIMEOUT: request timeout seconds (default: 30)
    - ANTHROPIC_MAX_TOKENS: max tokens to generate (default: 256)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Final

DEFAULT_MODEL: Final[str] = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
DEFAULT_TIMEOUT_S: Final[int] = int(os.getenv("ANTHROPIC_TIMEOUT", "30"))
DEFAULT_MAX_TOKENS: Final[int] = int(os.getenv("ANTHROPIC_MAX_TOKENS", "256"))
DEFAULT_API_URL: Final[str] = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_API_URL",
    "anthropic_chat",
]


def anthropic_chat(
    *,
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Call Anthropic Messages API and return the assistant text content."""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [
            {"role": "user", "content": user},
        ],
    }

    request = urllib.request.Request(
        DEFAULT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        raise RuntimeError(f"Anthropic request failed: {exc}") from exc

    blocks = data.get("content")
    if not isinstance(blocks, list):
        raise RuntimeError(f"Unexpected Anthropic response: {data}")

    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            texts.append(block["text"])

    content = "".join(texts).strip()
    if not content:
        raise RuntimeError(f"Unexpected Anthropic content blocks: {blocks}")
    return content
