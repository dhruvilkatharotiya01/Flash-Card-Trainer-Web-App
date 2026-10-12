"""Spaced repetition with the Leitner system.

Every card sits in one of five boxes. A correct answer moves it one box up, a
wrong answer sends it back to box 1. The box decides how long to wait before
the card is shown again, so well-known cards come back rarely and difficult
cards come back soon.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# days until the next review for boxes 1..5
INTERVALS_DAYS = (0, 1, 3, 7, 14)
MAX_BOX = len(INTERVALS_DAYS)


def schedule(card: dict, correct: bool, now: datetime | None = None) -> dict:
    """Update ``card`` in place after a review and return it."""
    now = now or datetime.now()
    box = int(card.get("box", 1))
    box = min(box + 1, MAX_BOX) if correct else 1
    card["box"] = box
    card["due"] = (now + timedelta(days=INTERVALS_DAYS[box - 1])).isoformat(timespec="seconds")
    card["reviews"] = int(card.get("reviews", 0)) + 1
    card["correct"] = int(card.get("correct", 0)) + int(correct)
    return card


def is_due(card: dict, now: datetime | None = None) -> bool:
    """A card that was never reviewed is always due."""
    due = card.get("due")
    return due is None or datetime.fromisoformat(due) <= (now or datetime.now())


def due_cards(cards: list[dict], now: datetime | None = None) -> list[dict]:
    """Cards to review now, hardest (lowest box) first."""
    return sorted((c for c in cards if is_due(c, now)), key=lambda c: int(c.get("box", 1)))
