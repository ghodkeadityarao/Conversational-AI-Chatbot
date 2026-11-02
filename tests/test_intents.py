from datetime import datetime, timezone

import pytest

from chatbot import intents

NOW = datetime(2026, 11, 1, 10, 5, tzinfo=timezone.utc)


def quick(message, name=None, tz=None):
    return intents.quick_answer(message, name, tz, NOW)


@pytest.mark.parametrize("message", ["What time is it?", "what's the current time", "Tell me the time", "time please", "Hey, what is the time now?",
                                     "Could you tell me what time it is", "WHAT TIME IS IT RIGHT NOW!!", "do you know what time it is"])
def test_requests_for_the_time_are_answered_locally(message):
    assert quick(message, tz="Asia/Kolkata").reply == "It's 3:35 PM on Sunday, 1 November 2026 (Asia/Kolkata)."


@pytest.mark.parametrize("message", ["What time did the Roman Empire fall?", "What time does the movie start?", "Explain time dilation",
                                     "What's the best time to visit Japan?", "How much time does it take to learn Python?",
                                     "What is the current time zone in Brazil?", "Is it time to buy a house?"])
def test_questions_that_only_contain_time_words_go_to_the_model(message):
    assert quick(message) is None


def test_the_time_uses_the_visitors_zone_and_falls_back_to_utc():
    assert "(UTC)" in quick("what time is it").reply and "10:05 AM" in quick("what time is it").reply
    assert "(UTC)" in quick("what time is it", tz="Not/AZone").reply
    assert "(UTC)" in quick("what time is it", tz="../../etc/passwd").reply
    assert "(America/New_York)" in quick("what time is it", tz="America/New_York").reply


@pytest.mark.parametrize("message", ["What day is it today?", "what's the date today", "today's date", "What is the date?"])
def test_the_date_is_answered_locally(message):
    assert quick(message, tz="Asia/Kolkata").reply == "Today is Sunday, 1 November 2026 (Asia/Kolkata)."


@pytest.mark.parametrize("message", ["what's the weather today", "weather in Paris", "Is it going to rain tomorrow?", "How's the weather outside",
                                     "weather", "what is the temperature right now", "Will it snow this weekend?"])
def test_weather_requests_get_an_honest_answer_without_the_model(message):
    reply = quick(message).reply
    assert reply and "live weather" in reply


@pytest.mark.parametrize("message", ["What causes rain?", "Explain the weather cycle", "write a poem about the weather", "how do weather balloons work",
                                     "weather vs climate: what's the difference?", "what's a good weather app to build in flask",
                                     "What was the weather like during the Battle of Waterloo?", "What temperature does water boil at?"])
def test_questions_about_weather_as_a_topic_go_to_the_model(message):
    assert quick(message) is None


@pytest.mark.parametrize("message,name", [("My name is Sam", "Sam"), ("my name is aditya rao.", "Aditya Rao"), ("Hi, my name's Priya!", "Priya"),
                                          ("Call me Alex", "Alex"), ("You can call me dr strange", "Dr Strange"), ("MY NAME IS SAM", "SAM"),
                                          ("my name is sam and i like football", "Sam")])
def test_a_name_is_captured_in_any_case_and_without_punctuation(message, name):
    q = quick(message)
    assert q.name == name and (q.reply is None or name in q.reply)


def test_a_name_followed_by_a_question_is_remembered_and_the_question_goes_on():
    q = quick("My name is Sam. What's the capital of France?")
    assert q.name == "Sam" and q.reply is None


def test_a_name_alone_gets_a_greeting():
    assert quick("my name is Sam").reply == "Nice to meet you, Sam! How can I help today?"


@pytest.mark.parametrize("message", ["My name is not important", "Why do people say my name is in interviews?", "my name is", "my name is 12345",
                                     "call me when you can", "Hello there"])
def test_things_that_are_not_names_are_left_alone(message):
    q = quick(message)
    assert q is None or q.name is None


def test_the_bot_can_say_or_forget_the_name():
    assert quick("what's my name?", name="Sam").reply == "Your name is Sam."
    assert "haven't told me" in quick("what is my name").reply
    q = quick("please forget my name", name="Sam")
    assert q.forget_name and "forgotten" in q.reply
