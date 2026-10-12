"""Lenient answer checking: ignores case, surrounding spaces, punctuation and articles."""

from __future__ import annotations

import re
import unicodedata

_ARTICLES = {"a", "an", "the"}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    words = re.findall(r"\w+", text)
    return " ".join(w for w in words if w not in _ARTICLES)


def is_correct(given: str, expected: str) -> bool:
    return bool(normalise(given)) and normalise(given) == normalise(expected)
