import unittest

from planner.ratelimit import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [0.0]

    def limiter(self, **kwargs: int) -> RateLimiter:
        return RateLimiter(clock=lambda: self.now[0], **kwargs)  # type: ignore[arg-type]

    def test_blocks_after_limit_and_recovers_when_window_slides(self) -> None:
        limiter = self.limiter(limit=2, window=10)
        self.assertEqual([limiter.allow("a") for _ in range(3)], [True, True, False])
        self.now[0] = 11.0
        self.assertTrue(limiter.allow("a"))

    def test_clients_are_independent(self) -> None:
        limiter = self.limiter(limit=1, window=10)
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

    def test_blocked_attempts_do_not_extend_the_block(self) -> None:
        limiter = self.limiter(limit=1, window=10)
        limiter.allow("a")
        self.now[0] = 9.0
        self.assertFalse(limiter.allow("a"))
        self.now[0] = 10.5
        self.assertTrue(limiter.allow("a"))

    def test_tracked_keys_are_bounded(self) -> None:
        limiter = self.limiter(limit=1, window=1, max_keys=5)
        for i in range(5):
            limiter.allow(str(i))
        self.now[0] = 100.0
        limiter.allow("fresh")
        self.assertLessEqual(len(limiter._hits), 2)

    def test_active_keys_survive_eviction(self) -> None:
        limiter = self.limiter(limit=1, window=100, max_keys=2)
        limiter.allow("a")
        limiter.allow("b")
        limiter.allow("c")           # triggers eviction, but a and b are still inside the window
        self.assertFalse(limiter.allow("a"))


if __name__ == "__main__":
    unittest.main()
