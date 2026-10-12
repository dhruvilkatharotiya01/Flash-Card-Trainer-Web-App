"""JSON file storage for decks and cards.

The whole collection is small, so it is kept in one JSON file. Writes go to a
temporary file that is then renamed, so a crash never leaves a half-written
file behind, and a lock serialises writes from concurrent requests.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from pathlib import Path

CARD_COLORS = ("#f28b82", "#fbbc04", "#fff475", "#ccff90", "#a7ffeb", "#cbf0f8", "#aecbfa", "#d7aefb")
MAX_DECK_NAME = 60


class NotFound(KeyError):
    """Raised when a deck or card does not exist."""


class Store:
    def __init__(self, path: str | Path, seed: str | Path | None = None) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        if not self.path.exists():
            data = json.loads(Path(seed).read_text(encoding="utf-8")) if seed else {"decks": {}}
            self._write(self._migrate(data))

    # ----------------------------------------------------------------- file io
    def _read(self) -> dict:
        try:
            return self._migrate(json.loads(self.path.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"decks": {}}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    @staticmethod
    def _migrate(data: dict) -> dict:
        """Accept the original format ``{deck: [cards]}`` and give every card an id."""
        if "decks" not in data:
            data = {"decks": data}
        for i, cards in enumerate(data["decks"].values()):
            for j, card in enumerate(cards):
                card.setdefault("id", uuid.uuid4().hex[:12])
                card.setdefault("hint", "")
                card.setdefault("color", CARD_COLORS[(i + j) % len(CARD_COLORS)])
        return data

    # ------------------------------------------------------------------- decks
    def decks(self) -> dict[str, list[dict]]:
        return self._read()["decks"]

    def deck(self, name: str) -> list[dict]:
        decks = self.decks()
        if name not in decks:
            raise NotFound(name)
        return decks[name]

    def create_deck(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Deck name is required.")
        if len(name) > MAX_DECK_NAME:
            raise ValueError(f"Deck name can have at most {MAX_DECK_NAME} characters.")
        with self._lock:
            data = self._read()
            if name in data["decks"]:
                raise ValueError(f"A deck called '{name}' already exists.")
            data["decks"][name] = []
            self._write(data)

    def delete_deck(self, name: str) -> None:
        with self._lock:
            data = self._read()
            if data["decks"].pop(name, None) is None:
                raise NotFound(name)
            self._write(data)

    # ------------------------------------------------------------------- cards
    def add_card(self, deck: str, question: str, answer: str, hint: str = "") -> dict:
        question, answer = question.strip(), answer.strip()
        if not question or not answer:
            raise ValueError("Question and answer are required.")
        with self._lock:
            data = self._read()
            if deck not in data["decks"]:
                raise NotFound(deck)
            cards = data["decks"][deck]
            card = {
                "id": uuid.uuid4().hex[:12],
                "question": question,
                "answer": answer,
                "hint": hint.strip(),
                "color": CARD_COLORS[len(cards) % len(CARD_COLORS)],
            }
            cards.append(card)
            self._write(data)
            return card

    def get_card(self, deck: str, card_id: str) -> dict:
        for card in self.deck(deck):
            if card["id"] == card_id:
                return card
        raise NotFound(card_id)

    def update_card(self, deck: str, card_id: str, **fields: str | int | None) -> dict:
        for key in ("question", "answer"):
            if key in fields and not str(fields[key]).strip():
                raise ValueError("Question and answer are required.")
        with self._lock:
            data = self._read()
            for card in data["decks"].get(deck, []):
                if card["id"] == card_id:
                    card.update({k: v.strip() if isinstance(v, str) else v for k, v in fields.items()})
                    self._write(data)
                    return card
            raise NotFound(card_id)

    def delete_card(self, deck: str, card_id: str) -> None:
        with self._lock:
            data = self._read()
            cards = data["decks"].get(deck)
            if cards is None:
                raise NotFound(deck)
            remaining = [c for c in cards if c["id"] != card_id]
            if len(remaining) == len(cards):
                raise NotFound(card_id)
            data["decks"][deck] = remaining
            self._write(data)
