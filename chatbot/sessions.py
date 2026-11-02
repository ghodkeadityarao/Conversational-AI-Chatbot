"""Per-visitor chat state and the limits that protect the API key.

Everything is kept in this process's memory, so run a single worker process (threads are fine).
"""
import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Session:
    sid: str
    history: list = field(default_factory=list)       # [(role, text)], role 'user' or 'model'
    name: str | None = None
    questions: int = 0                                # model calls made, kept across "new chat"
    last_seen: float = field(default_factory=time.time)

    def add(self, user_text, reply_text, limit):
        self.history += [("user", user_text), ("model", reply_text)]
        if len(self.history) > limit:
            self.history = self.history[-limit:]
            while self.history and self.history[0][0] != "user":     # always start on a user turn
                self.history.pop(0)

    def reset(self):
        self.history, self.name = [], None


class SessionStore:
    def __init__(self, ttl, max_sessions, clock=time.time):
        self.ttl, self.max_sessions, self.clock = ttl, max_sessions, clock
        self._items, self._lock = OrderedDict(), threading.Lock()

    def get(self, sid):
        """The visitor's session for a cookie value, creating a new one when it is missing, unknown or expired."""
        with self._lock:
            now = self.clock()
            for old in [k for k, s in self._items.items() if now - s.last_seen > self.ttl]:
                del self._items[old]
            session = self._items.get(sid) if sid else None
            if session is None:
                session = Session(secrets.token_urlsafe(24))
                self._items[session.sid] = session
                while len(self._items) > self.max_sessions:
                    self._items.popitem(last=False)
            session.last_seen = now
            self._items.move_to_end(session.sid)
            return session

    def __len__(self):
        return len(self._items)


class Limits:
    """Per-address request rate and a shared daily count of model calls."""

    def __init__(self, per_minute, per_day, clock=time.time, today=lambda: datetime.now(timezone.utc).date()):
        self.per_minute, self.per_day, self.clock, self.today = per_minute, per_day, clock, today
        self._hits, self._day, self._calls, self._lock = {}, None, 0, threading.Lock()

    def allow_request(self, address):
        """Seconds to wait if this address is over its rate, else 0."""
        with self._lock:
            now = self.clock()
            window = self._hits.setdefault(address, deque())
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return max(1, int(60 - (now - window[0])) + 1)
            window.append(now)
            if len(self._hits) > 5000:                                  # forget addresses that have gone quiet
                for key in [k for k, w in self._hits.items() if not w or now - w[-1] > 60]:
                    del self._hits[key]
            return 0

    def take_model_call(self):
        """True if the shared daily budget still has room (and uses one call of it)."""
        with self._lock:
            today = self.today()
            if today != self._day:
                self._day, self._calls = today, 0
            if self._calls >= self.per_day:
                return False
            self._calls += 1
            return True

    def give_back_model_call(self):
        with self._lock:
            self._calls = max(0, self._calls - 1)

