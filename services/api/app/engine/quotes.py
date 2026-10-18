"""Extract a clause quote from an official licence text. The repo never stores the text."""

from __future__ import annotations

import html
import re

_TAG = re.compile(r"(?is)<(script|style)\b.*?>.*?</\1>")
_ANY_TAG = re.compile(r"(?s)<[^>]+>")
_SPACE = re.compile(r"\s+")


def normalise_source(text: str, source_format: str) -> str:
    if source_format == "html":
        text = _TAG.sub(" ", text)
        text = _ANY_TAG.sub(" ", text)
        text = html.unescape(text)
    return _SPACE.sub(" ", text).strip()


def extract_quote(text: str, *, source_format: str, split_regex: str, locator: str) -> str | None:
    if not text or not locator:
        return None
    normalised = normalise_source(text, source_format)
    try:
        parts = re.split(split_regex, normalised)
    except re.error:
        parts = [normalised]
    pattern = re.compile(locator, re.IGNORECASE)
    for part in parts:
        piece = part.strip()
        if piece and pattern.search(piece):
            words = piece.split()
            if len(words) > 80:
                return " ".join(words[:80]) + " …"
            return piece
    return None
