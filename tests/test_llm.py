import pytest

from chatbot import llm


class Reason:
    def __init__(self, name):
        self.name = name


class Chunk:
    def __init__(self, text="", reason=None, block=None):
        self._text = text
        self.candidates = [type("C", (), {"finish_reason": Reason(reason) if reason else None})()]
        self.prompt_feedback = type("F", (), {"block_reason": block})() if block else None

    @property
    def text(self):
        return self._text


class FakeModels:
    def __init__(self, chunks=(), error=None, missing=()):
        self.chunks, self.error, self.missing, self.calls = chunks, error, set(missing), []

    def generate_content_stream(self, *, model, contents, config=None):
        self.calls.append((model, contents, config))
        if model in self.missing:
            raise ApiError(404, "models/x is not found")
        if self.error:
            raise self.error
        yield from self.chunks


class FakeClient:
    def __init__(self, **kw):
        self.models = FakeModels(**kw)


class ApiError(Exception):
    def __init__(self, code, message="secret details from google"):
        super().__init__(message)
        self.code = code


def run(client, history=(), message="hi", name=None):
    return list(llm.GeminiChat("key", "test-model", 256, client).stream(list(history), message, name))


def test_the_reply_is_streamed_in_pieces():
    assert run(FakeClient(chunks=[Chunk("Hel"), Chunk("lo!")])) == ["Hel", "lo!"]


def test_the_whole_conversation_and_the_name_are_sent_with_the_right_roles():
    client = FakeClient(chunks=[Chunk("ok")])
    run(client, [("user", "a"), ("model", "b")], "c", name="Sam")
    model, contents, config = client.models.calls[0]
    assert model == "test-model" and [c.role for c in contents] == ["user", "model", "user"]
    assert [c.parts[0].text for c in contents] == ["a", "b", "c"]
    assert "Sam" in config.system_instruction and "cannot see the current time" in config.system_instruction
    assert config.max_output_tokens == 256


@pytest.mark.parametrize("code,expected", [(429, "busy"), (401, "key"), (403, "key"), (404, "model"), (500, "server"), (503, "server"), (400, "other")])
def test_sdk_errors_become_plain_messages_and_never_leak_details(code, expected):
    with pytest.raises(llm.ChatError) as info:
        run(FakeClient(error=ApiError(code)))
    assert str(info.value) == llm.MESSAGES[expected] and "secret" not in str(info.value)


def test_an_invalid_key_reported_as_a_400_is_recognised():
    assert llm.classify(ApiError(400, "API key not valid. Please pass a valid API key.")) == "key"


def test_blocked_and_empty_replies_get_their_own_messages():
    with pytest.raises(llm.ChatError) as blocked:
        run(FakeClient(chunks=[Chunk("", reason="SAFETY")]))
    assert str(blocked.value) == llm.MESSAGES["blocked"]
    with pytest.raises(llm.ChatError) as feedback:
        run(FakeClient(chunks=[Chunk("", block="SAFETY")]))
    assert str(feedback.value) == llm.MESSAGES["blocked"]
    with pytest.raises(llm.ChatError) as empty:
        run(FakeClient(chunks=[Chunk("")]))
    assert str(empty.value) == llm.MESSAGES["empty"]


def test_a_chunk_whose_text_cannot_be_read_is_skipped():
    class Bad(Chunk):
        @property
        def text(self):
            raise ValueError("blocked")
    assert run(FakeClient(chunks=[Bad(), Chunk("fine")])) == ["fine"]


def test_without_a_key_chatting_explains_why():
    with pytest.raises(llm.ChatError, match="isn't set up"):
        list(llm.NoModel().stream([], "hi"))


def test_a_model_name_google_does_not_know_falls_back_to_the_next_one_and_is_remembered():
    client = FakeClient(chunks=[Chunk("ok")], missing=["test-model", "first-fallback"])
    chat = llm.GeminiChat("key", "test-model", 256, client, fallbacks=["first-fallback", "second-fallback"])
    assert list(chat.stream([], "hi")) == ["ok"]
    assert [c[0] for c in client.models.calls] == ["test-model", "first-fallback", "second-fallback"] and chat.model == "second-fallback"
    list(chat.stream([], "again"))
    assert client.models.calls[-1][0] == "second-fallback"                      # no repeat of the failed names


def test_when_every_model_is_missing_the_visitor_gets_the_model_message():
    client = FakeClient(missing=["test-model", "a", "b"])
    chat = llm.GeminiChat("key", "test-model", 256, client, fallbacks=["a", "b"])
    with pytest.raises(llm.ChatError) as info:
        list(chat.stream([], "hi"))
    assert str(info.value) == llm.MESSAGES["model"] and len(client.models.calls) == 3


def test_other_errors_do_not_trigger_a_model_change():
    client = FakeClient(error=ApiError(429))
    chat = llm.GeminiChat("key", "test-model", 256, client, fallbacks=["a"])
    with pytest.raises(llm.ChatError):
        list(chat.stream([], "hi"))
    assert [c[0] for c in client.models.calls] == ["test-model"]


def test_a_slow_model_call_that_times_out_gets_its_own_message():
    class ReadTimeout(Exception):
        pass
    assert llm.classify(ReadTimeout("x")) == "timeout" and llm.classify(ApiError(500, "request timed out")) == "timeout"
    with pytest.raises(llm.ChatError) as info:
        run(FakeClient(error=ReadTimeout("secret details")))
    assert str(info.value) == llm.MESSAGES["timeout"] and "secret" not in str(info.value)


def test_thinking_is_kept_short_only_for_model_families_that_support_it():
    from google.genai import types
    assert llm.thinking_config(types, "gemini-3.8-flash").thinking_level.name == "LOW"
    assert llm.thinking_config(types, "gemini-2.5-flash").thinking_budget == 0
    assert llm.thinking_config(types, "gemini-2.5-flash-lite") is None and llm.thinking_config(types, "other-model") is None


def test_the_thinking_setting_is_sent_and_dropped_if_the_model_rejects_it():
    client = FakeClient(chunks=[Chunk("ok")])
    run(client)                                                          # 'test-model' has no thinking setting
    assert client.models.calls[0][2].thinking_config is None
    seen = []

    class Rejecting(FakeModels):
        def generate_content_stream(self, *, model, contents, config=None):
            seen.append(config.thinking_config)
            if config.thinking_config is not None:
                raise ApiError(400, "Thinking level is not supported for this model")
            yield Chunk("fine")

    c = FakeClient()
    c.models = Rejecting()
    assert list(llm.GeminiChat("k", "gemini-3.8-flash", 64, c).stream([], "hi")) == ["fine"]
    assert seen[0] is not None and seen[1] is None


def test_the_log_message_for_an_error_never_contains_a_key():
    assert "AIza" not in llm._safe(ApiError(400, "bad key AIzaSyA1234567890abcdefghijklmnopqrstu in request"))
