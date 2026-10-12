"""HTTP routes."""

from __future__ import annotations

import random

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from .answers import is_correct
from .scheduler import due_cards, schedule
from .storage import Store

bp = Blueprint("main", __name__)


def store() -> Store:
    return current_app.extensions["store"]


@bp.get("/")
def home():
    decks = store().decks()
    summary = [{"name": n, "total": len(c), "due": len(due_cards(c))} for n, c in decks.items()]
    return render_template("home.html", decks=summary)


@bp.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------- decks
@bp.post("/decks")
def create_deck():
    name = request.form.get("name", "")
    try:
        store().create_deck(name)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.home"))
    flash(f"Deck '{name.strip()}' created. Add your first card.", "success")
    return redirect(url_for("main.deck", name=name.strip()))


@bp.get("/decks/<name>")
def deck(name: str):
    cards = store().deck(name)
    return render_template("deck.html", name=name, cards=cards, due=len(due_cards(cards)))


@bp.post("/decks/<name>/delete")
def delete_deck(name: str):
    store().delete_deck(name)
    flash(f"Deck '{name}' deleted.", "success")
    return redirect(url_for("main.home"))


# ------------------------------------------------------------------- cards
@bp.post("/decks/<name>/cards")
def add_card(name: str):
    f = request.form
    try:
        store().add_card(name, f.get("question", ""), f.get("answer", ""), f.get("hint", ""))
        flash("Card added.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.deck", name=name))


@bp.route("/decks/<name>/cards/<card_id>/edit", methods=["GET", "POST"])
def edit_card(name: str, card_id: str):
    card = store().get_card(name, card_id)
    if request.method == "POST":
        f = request.form
        try:
            store().update_card(
                name,
                card_id,
                question=f.get("question", ""),
                answer=f.get("answer", ""),
                hint=f.get("hint", ""),
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("edit_card.html", name=name, card={**card, **f.to_dict()})
        flash("Card updated.", "success")
        return redirect(url_for("main.deck", name=name))
    return render_template("edit_card.html", name=name, card=card)


@bp.post("/decks/<name>/cards/<card_id>/delete")
def delete_card(name: str, card_id: str):
    store().delete_card(name, card_id)
    flash("Card deleted.", "success")
    return redirect(url_for("main.deck", name=name))


# ------------------------------------------------------------------- study (spaced repetition)
@bp.route("/decks/<name>/study", methods=["GET", "POST"])
def study(name: str):
    cards = store().deck(name)
    result = None
    if request.method == "POST":
        card = store().get_card(name, request.form["card_id"])
        if request.form.get("action") == "reveal":
            correct = False
        else:
            correct = is_correct(request.form.get("answer", ""), card["answer"])
        updated = schedule(dict(card), correct)
        store().update_card(name, card["id"], **{k: updated[k] for k in ("box", "due", "reviews", "correct")})
        result = {"correct": correct, "card": card, "given": request.form.get("answer", "")}
        cards = store().deck(name)

    queue = due_cards(cards)
    if result:  # don't show the card that was just answered again straight away
        queue = [c for c in queue if c["id"] != result["card"]["id"]] or queue
    return render_template(
        "study.html", name=name, card=queue[0] if queue else None, remaining=len(queue), result=result
    )


# ------------------------------------------------------------------- exam
def _exam() -> dict | None:
    return session.get("exam")


@bp.post("/decks/<name>/exam")
def start_exam(name: str):
    cards = store().deck(name)
    if not cards:
        flash("Add some cards before taking an exam.", "error")
        return redirect(url_for("main.deck", name=name))
    order = [c["id"] for c in cards]
    if request.form.get("shuffle"):
        random.shuffle(order)
    session["exam"] = {
        "deck": name,
        "order": order,
        "index": 0,
        "revealed": False,
        "scores": {"right": 0, "wrong": 0, "skipped": 0},
        "last": None,
    }
    return redirect(url_for("main.exam", name=name))


@bp.route("/decks/<name>/exam/run", methods=["GET", "POST"])
def exam(name: str):
    state = _exam()
    if not state or state["deck"] != name:
        return redirect(url_for("main.deck", name=name))
    if state["index"] >= len(state["order"]):
        return redirect(url_for("main.exam_results", name=name))

    card = store().get_card(name, state["order"][state["index"]])
    if request.method == "POST":
        action = request.form.get("action")
        if action == "submit":
            given = request.form.get("answer", "")
            ok = is_correct(given, card["answer"])
            state["scores"]["right" if ok else "wrong"] += 1
            state["last"] = {"correct": ok, "given": given, "answer": card["answer"]}
            state["index"] += 1
            state["revealed"] = False
        elif action == "reveal" and not state["revealed"]:
            state["scores"]["skipped"] += 1
            state["revealed"] = True
            state["last"] = None
        elif action == "next":
            state["index"] += 1
            state["revealed"] = False
            state["last"] = None
        session["exam"] = state  # reassign so Flask stores the nested changes
        return redirect(url_for("main.exam", name=name))

    last = state.pop("last", None)
    session["exam"] = state
    return render_template(
        "exam.html",
        name=name,
        card=card,
        state=state,
        last=last,
        number=state["index"] + 1,
        total=len(state["order"]),
    )


@bp.get("/decks/<name>/exam/results")
def exam_results(name: str):
    state = _exam()
    if not state or state["deck"] != name:
        return redirect(url_for("main.deck", name=name))
    scores, total = state["scores"], len(state["order"])
    percent = round(100 * scores["right"] / total) if total else 0
    return render_template("results.html", name=name, scores=scores, total=total, percent=percent)
