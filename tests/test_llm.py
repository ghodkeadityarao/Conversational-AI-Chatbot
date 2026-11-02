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
    def __init__(self, chunks=(), error=None):
        self.chunks, self.error, self.calls = chunks, error, []

    def generate_content_stream(self, *, model, contents, config=None):
        self.calls.append((model, contents, config))
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
