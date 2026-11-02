"""The Gemini model behind the chat, with plain-language errors.

Messages are sent as the whole conversation each time (the server keeps each visitor's history), so no chat object is
shared between visitors. Nothing from the API's error messages reaches the page.
"""
import logging

log = logging.getLogger("chatbot")

SYSTEM_PROMPT = (
    "You are a friendly, concise assistant in a web chat. Answer clearly and directly, in the language the user writes in. "
    "Use Markdown sparingly: short lists and code blocks when they help. If you are not sure of something, say so instead of "
    "guessing. You cannot see the current time, date or weather and have no internet access, so do not claim to know them."
)


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
}


def classify(error):
    """The MESSAGES key for an exception raised by the SDK."""
    code = getattr(error, "code", None)
    text = str(error).lower()
    if code == 429:
        return "busy"
    if code in (401, 403) or "api key" in text and code == 400:
        return "key"
    if code == 404:
        return "model"
    if isinstance(code, int) and code >= 500:
        return "server"
    return "other"


class GeminiChat:
    def __init__(self, api_key, model, max_output_tokens=1024, client=None):
        self.model, self.max_output_tokens = model, max_output_tokens
        self._client, self._api_key = client, api_key

    @property
    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def stream(self, history, message, name=None):
        """Yield the reply in pieces. `history` is [(role, text)] with role 'user' or 'model'."""
        from google.genai import types
        contents = [types.Content(role=role, parts=[types.Part(text=text)]) for role, text in [*history, ("user", message)]]
        instruction = SYSTEM_PROMPT + (f" The user's name is {name}." if name else "")
        config = types.GenerateContentConfig(system_instruction=instruction, max_output_tokens=self.max_output_tokens)
        produced, blocked = False, False
        try:
            for chunk in self.client.models.generate_content_stream(model=self.model, contents=contents, config=config):
                text = _chunk_text(chunk)
                if text:
                    produced = True
                    yield text
                blocked = blocked or _was_blocked(chunk)
        except ChatError:
            raise
        except Exception as e:                           # the SDK raises its own error types; map them all
            kind = classify(e)
            log.warning("Gemini call failed (%s): %s", kind, type(e).__name__)
            raise ChatError(MESSAGES[kind]) from None
        if not produced:
            raise ChatError(MESSAGES["blocked" if blocked else "empty"])


def _chunk_text(chunk):
    try:
        return chunk.text or ""
    except Exception:                                    # a blocked chunk can raise when its text is read
        return ""


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
