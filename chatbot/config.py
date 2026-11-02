"""Settings, read from environment variables so nothing secret lives in the code."""
import os
from dataclasses import dataclass


def _int(env, name, default):
    try:
        return max(1, int(env.get(name, default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    api_key: str | None = None
    model: str = "gemini-3.8-flash"
    questions_per_session: int = 30          # model calls one visitor can make
    requests_per_minute: int = 15            # all messages from one network address
    model_calls_per_day: int = 1000          # all visitors together, to protect the API quota
    max_input_chars: int = 2000
    max_history_messages: int = 24
    max_output_tokens: int = 1024
    session_ttl_seconds: int = 2 * 60 * 60
    max_sessions: int = 2000

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        key = (env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY") or "").strip().strip("\"'")
        if key.lower().startswith(("your", "paste", "changeme", "xxx")):        # a copied placeholder is not a key
            key = ""
        d = cls()
        return cls(
            api_key=key or None,
            model=(env.get("GEMINI_MODEL") or d.model).strip(),
            questions_per_session=_int(env, "QUESTIONS_PER_SESSION", d.questions_per_session),
            requests_per_minute=_int(env, "REQUESTS_PER_MINUTE", d.requests_per_minute),
            model_calls_per_day=_int(env, "MODEL_CALLS_PER_DAY", d.model_calls_per_day),
            max_input_chars=_int(env, "MAX_INPUT_CHARS", d.max_input_chars),
            max_history_messages=_int(env, "MAX_HISTORY_MESSAGES", d.max_history_messages),
            max_output_tokens=_int(env, "MAX_OUTPUT_TOKENS", d.max_output_tokens),
            session_ttl_seconds=_int(env, "SESSION_TTL_SECONDS", d.session_ttl_seconds),
            max_sessions=_int(env, "MAX_SESSIONS", d.max_sessions),
        )
