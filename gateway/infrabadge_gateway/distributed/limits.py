"""Finite token bucket adapted from the PR5 design; no attacker-keyed maps."""

import threading
import time


class Budget:
    def __init__(self, per_minute, burst, clock=time.monotonic):
        self.rate, self.burst, self.tokens = per_minute / 60, burst, float(burst)
        self.clock, self.last, self.lock = clock, clock(), threading.Lock()

    def take(self):
        with self.lock:
            now = self.clock()
            self.tokens = min(self.burst, self.tokens + max(0, now - self.last) * self.rate)
            self.last = now
            if self.tokens < 1:
                return False
            self.tokens -= 1
            return True
