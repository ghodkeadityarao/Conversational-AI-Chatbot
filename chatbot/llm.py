"""The Gemini model behind the chat, with plain-language errors.

Messages are sent as the whole conversation each time (the server keeps each visitor's history), so no chat object is
shared between visitors. Nothing from the API's error messages reaches the page.
"""
import logging
import time

log = logging.getLogger("chatbot")

SYSTEM_PROMPT = (
    "You are a friendly assistant in a web chat. Give complete answers: short for simple questions, thorough with all the steps or items "
    "when the user asks for an explanation, a list or how to do something, and always finish what you start. Reply in the language the user writes in. "
    "Use Markdown sparingly: short lists and code blocks when they help. If you are not sure of something, say so instead of "
    "guessing. You cannot see the current time, date or weather and have no internet access, so do not claim to know them."
)


# Tried in order (after the configured model) when Google reports that a model name is not found.
FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash"]


class Cut:
    """Yielded after the last piece when the model stopped because it reached the reply length limit."""


class ChatError(Exception):
    """A failure with a message that is safe and useful to show the visitor."""


MESSAGES = {
    "not_configured": "The chat model isn't set up on this server yet, so I can only answer simple things like the time. "
                      "The owner needs to add an API key.",
    "blocked": "I can't help with that request. Try rephrasing it.",
    "busy": "The model is busy or its free quota is used up right now. Please try again in a minute.",
    "key": "The server's API key isn't accepted by Google. The owner needs to check it.",
    "model": "The chat model isn't available. The owner needs to check the model name.",
    "server": "The model service is having trouble. Please try again shortly.",
    "other": "Something went wrong while answering. Please try again.",
    "empty": "I didn't get an answer from the model. Please try rephrasing.",
    "timeout": "The model took too long to answer. Please try again, or ask something shorter.",
}


def classify(error):
    """The MESSAGES key for an exception raised by the SDK."""
    code = getattr(error, "code", None)
    text = str(error).lower()
    if "timeout" in type(error).__name__.lower() or "timed out" in text:
        return "timeout"
    if code == 429:
        return "busy"
    if code in (401, 403) or "api key" in text and code == 400:
        return "key"
    if code == 404:
        return "model"
    if isinstance(code, int) and code >= 500:
        return "server"
    return "other"


def thinking_config(types, model):
    """Less hidden 'thinking' means the first word arrives sooner. Only set for model families that support it."""
    if model.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="LOW")
    if model.startswith("gemini-2.5-flash") and "lite" not in model:
        return types.ThinkingConfig(thinking_budget=0)
    return None


class GeminiChat:
    def __init__(self, api_key, model, max_output_tokens=1024, client=None, fallbacks=None, timeout_seconds=90):
        self.model, self.max_output_tokens, self.timeout_seconds = model, max_output_tokens, timeout_seconds
        self.fallbacks = FALLBACK_MODELS if fallbacks is None else fallbacks
        self._client, self._api_key = client, api_key

    @property
    def client(self):
        if self._client is None:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=self._api_key,
                                        http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)))      # milliseconds
        return self._client

    def stream(self, history, message, name=None):
        """Yield the reply in pieces. `history` is [(role, text)] with role 'user' or 'model'.

        If Google says the model name does not exist (a 404), the next model in the fallback list is tried, and the
        first one that works is kept for later messages.
        """
        from google.genai import types
        contents = [types.Content(role=role, parts=[types.Part(text=text)]) for role, text in [*history, ("user", message)]]
        instruction = SYSTEM_PROMPT + (f" The user's name is {name}." if name else "")
        candidates = [self.model] + [m for m in self.fallbacks if m != self.model]
        position = 0
        use_thinking = True
        started = time.time()
        while position < len(candidates):
            model = candidates[position]
            config = types.GenerateContentConfig(system_instruction=instruction, max_output_tokens=self.max_output_tokens,
                                                 thinking_config=thinking_config(types, model) if use_thinking else None)
            produced, blocked, sent, hit_limit = False, False, [], False
            try:
                for chunk in self.client.models.generate_content_stream(model=model, contents=contents, config=config):
                    text = _chunk_text(chunk)
                    if text:
                        if not produced:
                            log.info("%s: first words after %.1fs", model, time.time() - started)
                        produced = True
                        sent.append(text)
                        yield text
                    blocked = blocked or _was_blocked(chunk)
                    hit_limit = hit_limit or _finish_reason(chunk) == "MAX_TOKENS"
            except ChatError:
                raise
            except Exception as e:                       # the SDK raises its own error types; map them all
                kind = classify(e)
                log.warning("Gemini call with %s failed after %.1fs (%s, %s, code %s, %d characters already sent): %s", model,
                            time.time() - started, kind, type(e).__name__, getattr(e, "code", None), sum(map(len, sent)), _safe(e))
                if not produced and use_thinking and getattr(e, "code", None) == 400 and "thinking" in str(e).lower():
                    use_thinking = False                 # this model rejected the thinking setting: ask again without it
                    continue
                if kind == "model" and not produced and position + 1 < len(candidates):
                    position += 1                        # this model name is not available to the key: try the next one
                    continue
                raise ChatError(MESSAGES[kind]) from None
            if not produced:
                raise ChatError(MESSAGES["blocked" if blocked else "empty"])
            log.info("%s: answered in %.1fs%s", model, time.time() - started, " (stopped at the length limit)" if hit_limit else "")
            if hit_limit:
                yield Cut()
            if model != self.model:
                log.warning("Using %s instead of %s", model, self.model)
                self.model = model
            return


def _safe(error):
    """The start of an error message for the server log, with anything that looks like a key removed."""
    import re
    return re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "[key]", str(error))[:300]


def _chunk_text(chunk):
    try:
        return chunk.text or ""
    except Exception:                                    # a blocked chunk can raise when its text is read
        return ""


def _finish_reason(chunk):
    for candidate in getattr(chunk, "candidates", None) or []:
        reason = getattr(candidate, "finish_reason", None)
        if reason is not None:
            return getattr(reason, "name", str(reason))
    return None


def _was_blocked(chunk):
    feedback = getattr(chunk, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        return True
    for candidate in getattr(chunk, "candidates", None) or []:
        reason = getattr(candidate, "finish_reason", None)
        if reason is not None and getattr(reason, "name", str(reason)) in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}:
            return True
    return False


class NoModel:
    """Stands in when there is no API key: every attempt to chat explains why it cannot."""

    def stream(self, history, message, name=None):
        raise ChatError(MESSAGES["not_configured"])
        yield                                            # makes this a generator
