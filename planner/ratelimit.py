"""Sliding-window rate limiter."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Allow at most `limit` calls per `window` seconds for each client key.

    In-memory, so it is per process: fine for a single worker (see README, "Assumptions").
    The number of tracked keys is bounded so many distinct clients cannot exhaust memory.
    """

    def __init__(self, limit: int, window: float,
                 clock: Callable[[], float] = time.monotonic, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._max_keys = max_keys
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for `key` and return whether it is within the limit."""
        now = self._clock()
        with self._lock:
            if key not in self._hits and len(self._hits) >= self._max_keys:
                self._evict_idle(now)
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def _evict_idle(self, now: float) -> None:
        idle = [k for k, q in self._hits.items() if not q or now - q[-1] > self.window]
        for key in idle:
            del self._hits[key]
