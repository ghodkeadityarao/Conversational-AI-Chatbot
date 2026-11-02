import json

import pytest

from app import create_app
from chatbot.config import Settings
from chatbot.llm import ChatError


class FakeLLM:
    def __init__(self, pieces=("Hello", " there"), error=None):
        self.pieces, self.error, self.calls = pieces, error, []

    def stream(self, history, message, name=None):
        self.calls.append((list(history), message, name))
        if self.error:
            raise ChatError(self.error)
        yield from self.pieces


def make(llm=None, **settings):
    llm = llm or FakeLLM()
    return create_app(Settings(api_key="k", **settings), llm).test_client(), llm


def say(client, message, tz=None, **kw):
    r = client.post("/chat", json={"message": message, "tz": tz}, **kw)
    return r, ([json.loads(x) for x in r.get_data(as_text=True).splitlines()] if r.mimetype == "application/x-ndjson" else r.get_json())


def text(lines):
    return "".join(x.get("t", "") for x in lines)


def test_the_page_loads_and_sets_no_inline_scripts():
    client, _ = make()
    r = client.get("/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "<script>" not in html and 'style="' not in html
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_a_reply_streams_as_json_lines_and_ends_with_the_questions_left():
    client, _ = make(questions_per_session=5)
    r, lines = say(client, "hi")
    assert r.mimetype == "application/x-ndjson" and [x.get("t") for x in lines[:2]] == ["Hello", " there"]
    assert lines[-1] == {"done": True, "remaining": 4}


def test_each_visitor_has_a_private_conversation():
    llm = FakeLLM()
    a, _ = make(llm)
    app = create_app(Settings(api_key="k"), llm)
    a, b = app.test_client(), app.test_client()
    say(a, "my name is Sam. Remember a secret word: banana")
    say(a, "what was the word?")
    say(b, "what was the word?")
    assert llm.calls[1][0] and llm.calls[1][2] == "Sam"                       # A's second question carries A's history and name
    assert llm.calls[2][0] == [] and llm.calls[2][2] is None                  # B starts fresh


def test_the_history_grows_and_is_capped():
    client, llm = make(max_history_messages=4)
    for i in range(5):
        say(client, f"q{i}")
    assert len(llm.calls[-1][0]) <= 4 and llm.calls[-1][0][0][0] == "user"


def test_simple_questions_do_not_call_the_model_or_use_a_question():
    client, llm = make(questions_per_session=3)
    r, lines = say(client, "what time is it?", tz="Asia/Kolkata")
    assert "Asia/Kolkata" in text(lines) and llm.calls == [] and lines[-1]["remaining"] == 3
    r, lines = say(client, "what's the weather today")
    assert "live weather" in text(lines) and llm.calls == []


def test_a_name_with_a_question_is_remembered_and_the_question_reaches_the_model():
    client, llm = make()
    say(client, "My name is Sam. What's 2+2?")
    assert llm.calls[0][1] == "My name is Sam. What's 2+2?" and llm.calls[0][2] == "Sam"
    _, lines = say(client, "what's my name")
    assert "Sam" in text(lines)


def test_new_chat_clears_history_and_name_but_not_the_question_count():
    client, llm = make(questions_per_session=5)
    say(client, "my name is Sam. hello")
    r = client.post("/reset")
    assert r.get_json() == {"ok": True, "remaining": 4}
    say(client, "hi again")
    assert llm.calls[-1][0] == [] and llm.calls[-1][2] is None


def test_a_visitor_stops_at_the_question_limit_for_the_session():
    client, llm = make(questions_per_session=2)
    say(client, "one")
    say(client, "two")
    r, body = say(client, "three")
    assert r.status_code == 429 and body["remaining"] == 0 and len(llm.calls) == 2
    r, lines = say(client, "what time is it")                                  # simple answers still work
    assert r.status_code == 200 and "UTC" in text(lines)


def test_the_shared_daily_budget_is_enforced():
    llm = FakeLLM()
    app = create_app(Settings(api_key="k", model_calls_per_day=2), llm)
    for _ in range(2):
        say(app.test_client(), "hi")
    r, body = say(app.test_client(), "hi")
    assert r.status_code == 429 and "daily" in body["error"] and len(llm.calls) == 2


def test_too_many_requests_from_one_address_get_a_retry_after():
    client, _ = make(requests_per_minute=3)
    for _ in range(3):
        say(client, "hi")
    r, body = say(client, "hi")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1 and "too fast" in body["error"]


def test_a_failed_model_call_shows_a_plain_error_and_costs_nothing():
    client, _ = make(FakeLLM(error="The model is busy."), questions_per_session=3)
    r, lines = say(client, "hi")
    assert lines == [{"error": "The model is busy."}]
    _, lines = say(client, "what time is it")
    assert lines[-1]["remaining"] == 3


def test_without_a_key_chat_explains_and_simple_answers_still_work():
    client = create_app(Settings(api_key=None), None).test_client()
    _, lines = say(client, "tell me a joke")
    assert "isn't set up" in lines[0]["error"]
    _, lines = say(client, "what time is it")
    assert "UTC" in text(lines)
    assert client.get("/health").get_json() == {"ok": True, "model_configured": False}


@pytest.mark.parametrize("payload,status", [({}, 400), ({"message": "   "}, 400), ({"message": 5}, 400), ({"message": "x" * 3000}, 400)])
def test_bad_messages_are_refused(payload, status):
    client, _ = make()
    r = client.post("/chat", json=payload)
    assert r.status_code == status and r.get_json()["error"]


def test_only_json_is_accepted_and_huge_bodies_are_refused():
    client, _ = make()
    assert client.post("/chat", data="hi", content_type="text/plain").status_code == 415
    assert client.post("/chat", data="x" * 40000, content_type="application/json").status_code == 413


def test_the_session_cookie_is_http_only_and_not_reissued_each_time():
    client, _ = make()
    first = client.post("/chat", json={"message": "hi"})
    cookie = first.headers["Set-Cookie"]
    assert "sid=" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Set-Cookie" not in client.post("/chat", json={"message": "again"}).headers


@pytest.mark.parametrize("value,expected", [("AIzaSyExampleExampleExampleExampleExample", "AIzaSyExampleExampleExampleExampleExample"),
                                            ("your_google_api_key", None), ("", None), ("  \"abc123\"  ", "abc123")])
def test_settings_read_the_key_from_either_variable_and_ignore_placeholders(value, expected):
    assert Settings.from_env({"GEMINI_API_KEY": value}).api_key == expected
    assert Settings.from_env({"GOOGLE_API_KEY": value}).api_key == expected


def test_settings_have_sensible_defaults_and_ignore_bad_numbers():
    s = Settings.from_env({"QUESTIONS_PER_SESSION": "abc", "MODEL_CALLS_PER_DAY": "-5"})
    assert s.model == "gemini-3.8-flash" and s.questions_per_session == 30 and s.model_calls_per_day == 1
