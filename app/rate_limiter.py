import time
from collections import defaultdict
from fastapi import Request, HTTPException

class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 15, burst_limit: int = 5, burst_window_sec: float = 3.0):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.burst_window_sec = burst_window_sec
        # Maps key -> list of float timestamps
        self.history = defaultdict(list)
        self.enabled = True

    def check_rate_limit(self, key: str):
        if not self.enabled:
            return

        now = time.time()
        minute_ago = now - 60.0
        burst_ago = now - self.burst_window_sec

        # Prune old timestamps
        timestamps = [t for t in self.history[key] if t > minute_ago]
        self.history[key] = timestamps

        # 1. Burst Check (e.g. more than 5 requests within 3 seconds)
        recent_burst = [t for t in timestamps if t > burst_ago]
        if len(recent_burst) >= self.burst_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too Many Requests",
                    "reason": "Burst rate limit exceeded",
                    "retry_after_seconds": round(self.burst_window_sec, 1)
                }
            )

        # 2. Window Check (e.g. max 15 requests per minute)
        if len(timestamps) >= self.requests_per_minute:
            oldest = timestamps[0]
            retry_after = round(60.0 - (now - oldest), 1)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too Many Requests",
                    "reason": "Rate limit exceeded (15 req/min)",
                    "retry_after_seconds": max(1.0, retry_after)
                }
            )

        # Record this request
        self.history[key].append(now)

    def reset(self):
        self.history.clear()

# Global instance for public submission endpoint
submission_rate_limiter = SlidingWindowRateLimiter(requests_per_minute=15, burst_limit=5, burst_window_sec=2.0)
