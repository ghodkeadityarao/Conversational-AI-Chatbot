"""Quick answers that need no language model: the time, the date, weather requests, and remembering a name.

The rules match whole requests, not words anywhere in a sentence, so "What time did the Roman Empire fall?" goes to
the model and "what time is it" does not.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FILLER = re.compile(r"^(?:hey|hi|hello|ok|okay|so|um|please|can you|could you|would you|tell me|do you know|do you have|"
                    r"i want to know|i need to know|quick question)[ ,]+")
TIME = [
    r"what(?:'s| is)? (?:the )?(?:current |exact |local )?time(?: is it)?(?: now| right now| currently| at the moment)?",
    r"what time (?:it is|is it)(?: now| right now| currently)?",
    r"(?:the )?(?:current |exact |local )?time(?: now| right now| please)?",
]
DATE = [
    r"what(?:'s| is)? (?:the )?(?:today'?s )?date(?: today| now)?",
    r"what(?:'s| is)? today'?s date",
    r"today'?s date",
    r"what day (?:is it|is today)(?: today)?",
    r"what(?:'s| is) today",
]
WEATHER_WORD = re.compile(r"\b(?:weather|forecast)\b")
WEATHER_PHRASE = [
    re.compile(r"\b(?:will it|is it|are we|going to|gonna)\b.*\b(?:rain|raining|snow|snowing|storm|sunny|cloudy|hot|cold)\b"),
    re.compile(r"\btemperature\b.*\b(?:today|tomorrow|tonight|outside|right now|now|in [a-z]+)\b"),
]
WEATHER_CONTEXT = re.compile(r"\b(?:today|tomorrow|tonight|now|right now|currently|outside|this (?:week|weekend|morning|evening|"
                             r"afternoon)|like|going to be|in [a-z]+|at [a-z]+|here|there|how's|what's|what is|how is|check)\b")
NOT_A_WEATHER_REQUEST = re.compile(r"\b(?:explain|why|how do|how does|what causes|cycle|balloon|app|api|code|build|write|poem|story|"
                                   r"essay|difference|vs|versus|climate|define|meaning|history|historical|model|python|flask|"
                                   r"was|were|during|in (?:1[0-9]{3}|20[0-2][0-9]))\b")
NAME_LEAD = re.compile(r"^(?:(?:hi|hello|hey)[,!. ]+)?(?:my name is|my name's|i am called|i'm called|call me|you can call me)\s+(.+)$", re.I)
ASK_NAME = re.compile(r"^(?:what(?:'s| is) my name|who am i|do you (?:know|remember) (?:my name|who i am)|what do you call me)$")
FORGET_NAME = re.compile(r"^(?:please )?(?:forget|delete|remove) my name$")
NOT_NAMES = {"not", "what", "who", "a", "an", "the", "your", "none", "nobody", "unknown", "secret", "important", "private", "hidden",
             "is", "was", "and", "or", "but", "so", "when", "if", "later", "back", "at", "tomorrow", "maybe", "anytime", "now", "soon",
             "by", "on", "in", "before", "after", "once", "whenever", "something", "anything", "whatever", "sometime", "tonight", "today"}
WEATHER_REPLY = ("I don't have access to live weather data, so I can't give you current conditions or a forecast. A weather app or "
                 "your local weather service will have them. I'm happy to help with anything else, including how weather works.")


@dataclass
class Quick:
    reply: str | None = None          # the answer, or None to carry on to the language model
    name: str | None = None           # a name to remember
    forget_name: bool = False


def normalise(message):
    text = message.lower().replace("’", "'").strip()
    text = re.sub(r"[?!.]+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    while True:
        stripped = FILLER.sub("", text)
        if stripped == text:
            return text
        text = stripped


def zone(name):
    """A ZoneInfo for an IANA name such as 'Asia/Kolkata', or None if it is missing or not valid."""
    if not name or len(name) > 64 or not re.fullmatch(r"[A-Za-z0-9_+\-/]+", name):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def _now(tz_name, now):
    tz = zone(tz_name)
    moment = (now or datetime.now(timezone.utc)).astimezone(tz or timezone.utc)
    return moment, (tz_name if tz else "UTC")


def _day(moment):
    return f"{moment.strftime('%A')}, {moment.day} {moment.strftime('%B %Y')}"


def clock_reply(tz_name, now=None):
    moment, label = _now(tz_name, now)
    return f"It's {moment.strftime('%I:%M %p').lstrip('0')} on {_day(moment)} ({label})."


def date_reply(tz_name, now=None):
    moment, label = _now(tz_name, now)
    return f"Today is {_day(moment)} ({label})."


def asks_for_weather(text):
    if any(p.search(text) for p in WEATHER_PHRASE) and not NOT_A_WEATHER_REQUEST.search(text):
        return True
    if not WEATHER_WORD.search(text) or NOT_A_WEATHER_REQUEST.search(text):
        return False
    return len(text.split()) <= 3 or bool(WEATHER_CONTEXT.search(text))


def parse_name(rest):
    """(name, what is left of the message) from the text after 'my name is', or (None, rest) if it is not a name."""
    m = re.match(r"([A-Za-z][A-Za-z'\-]*(?: [A-Za-z][A-Za-z'\-]*){0,2})(.*)$", rest.strip())
    if not m:
        return None, rest
    words, tail = m.group(1).split(), m.group(2)
    kept = []
    for w in words:
        if w.lower() in NOT_NAMES and kept:             # "Sam and" -> "Sam"
            break
        kept.append(w)
    if not kept or kept[0].lower() in NOT_NAMES or len(" ".join(kept)) > 30:
        return None, rest
    leftover = " ".join(words[len(kept):]) + tail
    return " ".join(w[:1].upper() + w[1:] for w in kept), leftover.strip()


def quick_answer(message, name=None, tz_name=None, now=None):
    """A Quick for messages the bot can handle itself, or None to send the message to the language model."""
    text = normalise(message)
    if FORGET_NAME.match(text):
        return Quick("Okay, I've forgotten your name.", forget_name=True)
    if ASK_NAME.match(text):
        return Quick(f"Your name is {name}." if name else "You haven't told me your name yet. Say \"My name is ...\" and I'll remember it.")
    if any(re.fullmatch(p, text) for p in TIME):
        return Quick(clock_reply(tz_name, now))
    if any(re.fullmatch(p, text) for p in DATE):
        return Quick(date_reply(tz_name, now))
    m = NAME_LEAD.match(message.strip().replace("’", "'"))
    if m:
        who, leftover = parse_name(m.group(1))
        if who and "call me" in message.lower() and len(who.split()) > 2:       # "call me when you can" is not a name
            who = None
        if who:
            if re.fullmatch(r"[\s.,!?;:]*", leftover):
                return Quick(f"Nice to meet you, {who}! How can I help today?", name=who)
            return Quick(None, name=who)                 # remember the name, then answer the rest of the message
    if asks_for_weather(text):
        return Quick(WEATHER_REPLY)
    return None
