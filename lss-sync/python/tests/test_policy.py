"""Batching and retry decisions at their documented boundaries."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))
from lss_sync.policy import BatchPolicy, retry_after, retry_delay
from lss_sync.protocol import MAX_BATCH, MIN_BATCH


class BatchPolicyTests(unittest.TestCase):
    def test_modes_start_at_documented_bounds(self):
        self.assertEqual(BatchPolicy().bytes, MIN_BATCH)
        self.assertEqual(BatchPolicy("fixed-small").bytes, MIN_BATCH)
        self.assertEqual(BatchPolicy("fixed-large").bytes, MAX_BATCH)
        with self.assertRaises(ValueError):
            BatchPolicy("unbounded")

    def test_two_consecutive_full_acknowledged_batches_increase_by_2kib(self):
        policy = BatchPolicy()
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), 2048)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), 4096)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), 4096)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), 6144)

    def test_tail_or_partial_acknowledgement_resets_growth_streak(self):
        for interrupted in ({"full": False, "all_acknowledged": True},
                            {"full": True, "all_acknowledged": False}):
            with self.subTest(interrupted=interrupted):
                policy = BatchPolicy()
                policy.observe(full=True, all_acknowledged=True)
                policy.observe(**interrupted)
                self.assertEqual(policy.observe(full=True, all_acknowledged=True), MIN_BATCH)
                self.assertEqual(policy.observe(full=True, all_acknowledged=True), MIN_BATCH * 2)

    def test_success_growth_stops_at_16kib(self):
        policy = BatchPolicy()
        for _ in range(30):
            policy.observe(full=True, all_acknowledged=True, duration_ms=100)
        self.assertEqual(policy.bytes, MAX_BATCH)

    def test_failure_halves_limit_and_resets_growth_streak(self):
        policy = BatchPolicy()
        for _ in range(6):
            policy.observe(full=True, all_acknowledged=True)
        self.assertEqual(policy.bytes, 8192)
        policy.observe(full=True, all_acknowledged=True)
        self.assertEqual(policy.observe(transient_failure=True), 4096)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), 4096)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), 6144)
        self.assertEqual(policy.observe(transient_failure=True), 3072)
        self.assertEqual(policy.observe(transient_failure=True), MIN_BATCH)
        self.assertEqual(policy.observe(transient_failure=True), MIN_BATCH)

    def test_slow_boundary_is_strictly_over_eight_seconds(self):
        policy = BatchPolicy()
        policy.observe(full=True, all_acknowledged=True, duration_ms=8000)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True, duration_ms=8000), 4096)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True, duration_ms=8000.001), MIN_BATCH)

    def test_fixed_policies_ignore_both_successes_and_failures(self):
        for mode, expected in [("fixed-small", MIN_BATCH), ("fixed-large", MAX_BATCH)]:
            with self.subTest(mode=mode):
                policy = BatchPolicy(mode)
                for _ in range(4):
                    self.assertEqual(policy.observe(full=True, all_acknowledged=True), expected)
                    self.assertEqual(policy.observe(transient_failure=True, duration_ms=9000), expected)

    def test_mode_change_resets_limit_and_success_streak(self):
        policy = BatchPolicy()
        policy.observe(full=True, all_acknowledged=True)
        policy.set_mode("fixed-large")
        self.assertEqual(policy.bytes, MAX_BATCH)
        policy.set_mode("adaptive")
        self.assertEqual(policy.bytes, MIN_BATCH)
        self.assertEqual(policy.observe(full=True, all_acknowledged=True), MIN_BATCH)


class RetryTests(unittest.TestCase):
    def test_full_jitter_doubles_until_30_second_cap(self):
        for attempt, ceiling in [(0, 1000), (1, 1000), (2, 2000), (3, 4000),
                                  (5, 16000), (6, 30000), (1000000, 30000)]:
            with self.subTest(attempt=attempt):
                self.assertEqual(retry_delay(attempt, lambda: 0), 0)
                self.assertEqual(retry_delay(attempt, lambda: 0.5), ceiling // 2)
                self.assertEqual(retry_delay(attempt, lambda: 0.999999), ceiling - 1)

    def test_jitter_returns_integer_milliseconds(self):
        result = retry_delay(1, lambda: 0.123456)
        self.assertIs(type(result), int)
        self.assertEqual(result, 123)

    def test_retry_after_delta_seconds_and_fractional_seconds(self):
        now = 1_700_000_000_000
        self.assertEqual(retry_after("0", now), now)
        self.assertEqual(retry_after("2", now), now + 2000)
        self.assertEqual(retry_after(" 2.5 ", now), now + 2500)
        with patch("lss_sync.policy.time.time", return_value=1700000000):
            self.assertEqual(retry_after("3"), now + 3000)

    def test_retry_after_http_dates_use_utc_and_never_go_backwards(self):
        target = datetime(2026, 11, 18, 12, 30, tzinfo=timezone.utc).timestamp() * 1000
        self.assertEqual(retry_after("Wed, 18 Nov 2026 12:30:00 GMT", target - 5000), target)
        self.assertEqual(retry_after("Wed, 18 Nov 2026 12:30:00 +0000", target - 5000), target)
        self.assertEqual(retry_after("Wed, 18 Nov 2026 12:30:00", target - 5000), target)
        self.assertEqual(retry_after("Wed, 18 Nov 2026 12:30:00 GMT", target + 5000), target + 5000)

    def test_invalid_or_nonfinite_retry_after_values_are_ignored(self):
        for value in (None, "", " ", "-1", "NaN", "Infinity", "tomorrow", "1e3", "9" * 400):
            with self.subTest(value=value):
                self.assertEqual(retry_after(value, 1000), 0)

    def test_unrepresentable_retry_after_deadline_is_ignored(self):
        self.assertEqual(retry_after("1" + "0" * 307, 0), 0)


if __name__ == "__main__":
    unittest.main()
