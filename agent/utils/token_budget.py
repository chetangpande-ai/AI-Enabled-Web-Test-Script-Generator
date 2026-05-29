from __future__ import annotations

import re


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "i",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "page",
    "the",
    "then",
    "to",
    "with",
}


def compact_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def keyword_list(value: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (value or "").lower())
    keywords: list[str] = []
    for word in words:
        if len(word) < 2 or word in STOPWORDS or word in keywords:
            continue
        keywords.append(word)
        if len(keywords) >= limit:
            break
    return keywords

