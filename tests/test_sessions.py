from datetime import date

from chatbot.sessions import Limits, SessionStore


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_each_cookie_gets_its_own_session_and_a_missing_or_unknown_one_gets_a_new_id():
    store = SessionStore(3600, 10)
    a, b = store.get(None), store.get(None)
    assert a.sid != b.sid and store.get(a.sid) is a and store.get("made-up") is not a and len(a.sid) >= 30


def test_sessions_expire_and_the_oldest_are_dropped_when_there_are_too_many():
    clock = Clock()
    store = SessionStore(100, 3, clock)
    first = store.get(None)
    clock.t += 101
    assert store.get(first.sid) is not first                       # expired: a fresh session replaces it
    sessions = [store.get(None) for _ in range(5)]
    assert len(store) == 3 and store.get(sessions[0].sid) is not sessions[0]


def test_history_is_capped_and_always_starts_with_a_user_turn():
    s = SessionStore(3600, 10).get(None)
    for i in range(10):
        s.add(f"q{i}", f"a{i}", 6)
    assert len(s.history) <= 6 and s.history[0][0] == "user" and s.history[-1] == ("model", "a9")


def test_reset_clears_the_conversation_but_not_the_question_count():
    s = SessionStore(3600, 10).get(None)
    s.add("hi", "hello", 10)
    s.name, s.questions = "Sam", 4
    s.reset()
    assert s.history == [] and s.name is None and s.questions == 4


def test_the_per_address_rate_is_a_sliding_minute():
    clock = Clock()
    limits = Limits(3, 100, clock)
    assert [limits.allow_request("1.2.3.4") for _ in range(3)] == [0, 0, 0]
    assert limits.allow_request("1.2.3.4") > 0 and limits.allow_request("5.6.7.8") == 0
    clock.t += 61
    assert limits.allow_request("1.2.3.4") == 0


def test_the_daily_budget_resets_each_day_and_can_be_given_back():
    today = [date(2026, 11, 1)]
    limits = Limits(100, 2, Clock(), lambda: today[0])
    assert limits.take_model_call() and limits.take_model_call() and not limits.take_model_call()
    limits.give_back_model_call()
    assert limits.take_model_call()
    today[0] = date(2026, 11, 2)
    assert limits.take_model_call()
