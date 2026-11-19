"""Pure batching and retry rules shared by all LSS transports."""
from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
import math
import random as random_module
import re
import time
from .protocol import MIN_BATCH, MAX_BATCH


class BatchPolicy:
    def __init__(self, mode: str = "adaptive"):
        self.set_mode(mode)

    def set_mode(self, mode: str) -> None:
        if mode not in {"adaptive", "fixed-small", "fixed-large"}:
            raise ValueError("Unknown batching policy")
        self.mode = mode
        self.bytes = MAX_BATCH if mode == "fixed-large" else MIN_BATCH
        self.successes = 0

    def observe(self, *, transient_failure: bool = False, duration_ms: float = 0,
                full: bool = False, all_acknowledged: bool = False) -> int:
        if self.mode != "adaptive":
            return self.bytes
        if transient_failure or duration_ms > 8000:
            self.bytes = max(MIN_BATCH, self.bytes // 2)
            self.successes = 0
        elif full and all_acknowledged:
            self.successes += 1
            if self.successes == 2:
                self.bytes = min(MAX_BATCH, self.bytes + MIN_BATCH)
                self.successes = 0
        else:
            self.successes = 0
        return self.bytes


def retry_delay(attempt: int, random=random_module.random) -> int:
    """Return milliseconds of full jitter, capped at a 30-second ceiling."""
    return math.floor(min(30000, 1000 * 2 ** min(max(attempt - 1, 0), 15)) * random())


def retry_after(value: str | None, now_ms: float | None = None) -> float:
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    if not value:
        return 0
    if re.fullmatch(r"\d+(?:\.\d+)?", value.strip()):
        seconds = float(value)
        deadline = now_ms + seconds * 1000
        return deadline if math.isfinite(deadline) else 0
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(now_ms, parsed.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return 0
