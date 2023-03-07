import time
from unittest import TestCase, mock

from scripts.lib.check_rabbitmq_queue import CRITICAL, OK, UNKNOWN, WARNING, analyze_queue_stats


class AnalyzeQueueStatsTests(TestCase):
    def test_no_stats_available(self) -> None:
        result = analyze_queue_stats("name", {}, 0)
        self.assertEqual(result["status"], UNKNOWN)

    def test_queue_stuck(self) -> None:
        """Last update > 5 minutes ago and there's events in the queue."""

        result = analyze_queue_stats("name", {"update_time": time.time() - 301}, 100)
        self.assertEqual(result["status"], CRITICAL)
        self.assertIn("queue appears to be stuck", result["message"])

    def test_queue_just_started(self) -> None:
        """
        We just started processing a burst of events, and haven't processed enough
        to log productivity statistics yet.
        """
        result = analyze_queue_stats(
            "name",
            {
                "update_time": time.time(),
                "recent_average_consume_time": None,
            },
            10000,
        )
        self.assertEqual(result["status"], OK)

    def test_queue_normal(self) -> None:
        """10000 events and each takes a second => it'll take a long time to empty."""
        result = analyze_queue_stats(
            "name",
            {
                "update_time": time.time(),
                "queue_last_emptied_timestamp": time.time() - 10000,
                "recent_average_consume_time": 1,
            },
            10000,
        )
        self.assertEqual(result["status"], CRITICAL)
        self.assertIn("clearing the backlog", result["message"])

        # If we're doing 10K/sec, it's OK.
        result = analyze_queue_stats(
            "name",
            {
                "update_time": time.time(),
                "queue_last_emptied_timestamp": time.time() - 10000,
                "recent_average_consume_time": 0.0001,
            },
            10000,
        )
        self.assertEqual(result["status"], OK)

        # Verify logic around whether it'll take MAX_SECONDS_TO_CLEAR to clear queue.
        with mock.patch.dict("scripts.lib.check_rabbitmq_queue.MAX_SECONDS_TO_CLEAR", {"name": 10}):
            result = analyze_queue_stats(
                "name",
                {
                    "update_time": time.time(),
                    "queue_last_emptied_timestamp": time.time() - 10000,
                    "recent_average_consume_time": 1,
                },
                11,
            )
            self.assertEqual(result["status"], WARNING)
            self.assertIn("clearing the backlog", result["message"])

            result = analyze_queue_stats(
                "name",
                {
                    "update_time": time.time(),
                    "queue_last_emptied_timestamp": time.time() - 10000,
                    "recent_average_consume_time": 1,
                },
                9,
            )
            self.assertEqual(result["status"], OK)
