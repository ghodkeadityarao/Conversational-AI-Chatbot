"""A chatbot web app: simple questions are answered locally, everything else by Gemini, streamed to the page.

    flask --app app run

Each visitor has their own conversation (a random id in a cookie). Nothing is written to disk.
Keep it to one worker process: conversations and limits live in that process's memory.
"""
import json
import logging
import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

from chatbot import intents
from chatbot.config import Settings
from chatbot.llm import ChatError, GeminiChat, NoModel
from chatbot.sessions import Limits, SessionStore

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def line(**payload):
    return json.dumps(payload, ensure_ascii=False) + "\n"


def create_app(settings=None, llm=None, clock=None):
    settings = settings or Settings.from_env()
    if llm is None:
        llm = GeminiChat(settings.api_key, settings.model, settings.max_output_tokens, timeout_seconds=settings.model_timeout_seconds) if settings.api_key else NoModel()
    store = SessionStore(settings.session_ttl_seconds, settings.max_sessions, **({"clock": clock} if clock else {}))
    limits = Limits(settings.requests_per_minute, settings.model_calls_per_day, **({"clock": clock} if clock else {}))

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
    if os.environ.get("TRUST_PROXY") == "1":                                  # behind a proxy such as Render's
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    @app.after_request
    def secure(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy",
                                    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        return response

    def with_cookie(response, session):
        if request.cookies.get("sid") != session.sid:
            response.set_cookie("sid", session.sid, max_age=settings.session_ttl_seconds, httponly=True, samesite="Lax",
                                secure=request.is_secure)
        return response

    def remaining(session):
        return max(0, settings.questions_per_session - session.questions)

    def refuse(session, status, message, **extra):
        return with_cookie(jsonify(error=message, remaining=remaining(session), **extra), session), status

    @app.get("/")
    def index():
        return render_template("chat.html", limit=settings.questions_per_session, max_chars=settings.max_input_chars)

    @app.get("/health")
    def health():
        return jsonify(ok=True, model_configured=not isinstance(llm, NoModel))

    @app.post("/chat")
    def chat():
        session = store.get(request.cookies.get("sid"))
        if not request.is_json:
            return refuse(session, 415, "Send JSON.")
        data = request.get_json(silent=True)
        data = data if isinstance(data, dict) else {}
        message = data.get("message")
        message = message.strip() if isinstance(message, str) else ""
        if not message:
            return refuse(session, 400, "Type a message first.")
        if len(message) > settings.max_input_chars:
            return refuse(session, 400, f"That message is too long (the limit is {settings.max_input_chars} characters).")
        wait = limits.allow_request(request.remote_addr or "unknown")
        if wait:
            resp, status = refuse(session, 429, f"You're sending messages too fast. Wait {wait} seconds.", retry_after=wait)
            resp.headers["Retry-After"] = str(wait)
            return resp, status

        tz = data.get("tz") if isinstance(data.get("tz"), str) else None
        quick = intents.quick_answer(message, session.name, tz)
        if quick:
            if quick.forget_name:
                session.name = None
            if quick.name:
                session.name = quick.name
        if quick and quick.reply:
            session.add(message, quick.reply, settings.max_history_messages)
            body = line(t=quick.reply) + line(done=True, remaining=remaining(session))
            return with_cookie(Response(body, mimetype="application/x-ndjson", headers={"Cache-Control": "no-store"}), session)

        if session.questions >= settings.questions_per_session:
            return refuse(session, 429, f"You've used your {settings.questions_per_session} questions for this session. "
                                        "Time-limited sessions keep this free demo available for everyone.")
        if not limits.take_model_call():
            return refuse(session, 429, "The daily question budget for this demo is used up. Please come back tomorrow.")
        session.questions += 1
        history = list(session.history)

        def generate():
            parts = []
            yield line(start=True)                                                # sends the headers now, not after the first word
            try:
                for piece in llm.stream(history, message, session.name):
                    parts.append(piece)
                    yield line(t=piece)
            except ChatError as e:
                if not parts:                                                 # nothing was shown: it does not use a question
                    session.questions -= 1
                    limits.give_back_model_call()
                yield line(error=str(e), cut=bool(parts))
                return
            session.add(message, "".join(parts), settings.max_history_messages)
            yield line(done=True, remaining=remaining(session))

        return with_cookie(Response(generate(), mimetype="application/x-ndjson",
                                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}), session)

    @app.post("/reset")
    def reset():
        session = store.get(request.cookies.get("sid"))
        session.reset()
        return with_cookie(jsonify(ok=True, remaining=remaining(session)), session)

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(error="That request is too large."), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5000)
