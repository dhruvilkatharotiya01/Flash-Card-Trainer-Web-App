"""Flashcard trainer: decks, cards, spaced-repetition study and exams (Flask)."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask, abort, render_template, request, session

from .storage import NotFound, Store

__version__ = "1.0.0"

ROOT = Path(__file__).resolve().parent.parent


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATA_FILE=os.environ.get("FLASHCARDS_DATA", str(ROOT / "instance" / "flashcards.json")),
        SEED_FILE=str(ROOT / "data" / "demo_decks.json"),
        CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)

    app.extensions["store"] = Store(app.config["DATA_FILE"], seed=app.config["SEED_FILE"])

    @app.context_processor
    def inject_csrf() -> dict:
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return {"csrf_token": session["csrf"]}

    @app.before_request
    def check_csrf() -> None:
        if request.method == "POST" and app.config["CSRF_ENABLED"]:
            token = request.form.get("csrf_token", "")
            if not token or not secrets.compare_digest(token, session.get("csrf", "")):
                abort(400, "Invalid or missing form token. Reload the page and try again.")

    @app.errorhandler(NotFound)
    def not_found(_: NotFound):
        return render_template("error.html", code=404, message="That deck or card does not exist."), 404

    @app.errorhandler(400)
    @app.errorhandler(404)
    def http_error(err):
        return render_template("error.html", code=err.code, message=err.description), err.code

    from .routes import bp

    app.register_blueprint(bp)
    return app
