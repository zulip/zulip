import time
from unittest import TestCase, mock

from scripts.lib.check_rabbitmq_queue import CRITICAL, OK, UNKNOWN, WARNING, analyze_queue_stats


class AnalyzeQueueStatsTests(TestCase):
    def test_no_stats_available(self) -> None:
        result = analyze_queue_stats('name', {}, 0)
        self.assertEqual(result['status'], UNKNOWN)

    def test_queue_stuck(self) -> None:
        """Last update > 5 minutes ago and there's events in the queue.

        In theory, we could be having bad luck with a race where in
        the last (event_handing_time * 50) a burst was added, but it's
        unlikely and shouldn't fail 2 in a row for Nagios anyway.
        """
        result = analyze_queue_stats('name', {'update_time': time.time() - 301}, 100)
        self.assertEqual(result['status'], CRITICAL)
        self.assertIn('queue appears to be stuck', result['message'])

    def test_queue_just_started(self) -> None:
        """
        We just started processing a burst of events, and haven't processed enough
        to log productivity statistics yet.
        """
        result = analyze_queue_stats('name', {'update_time': time.time(),
                                              'current_queue_size': 10000,
                                              'recent_average_consume_time': None}, 10000)
        self.assertEqual(result['status'], OK)

    def test_queue_normal(self) -> None:
        """10000 events and each takes a second => it'll take a long time to empty."""
        result = analyze_queue_stats('name', {'update_time': time.time(),
                                              'current_queue_size': 10000,
                                              'queue_last_emptied_timestamp': time.time() - 10000,
                                              'recent_average_consume_time': 1}, 10000)
        self.assertEqual(result['status'], CRITICAL)
        self.assertIn('clearing the backlog', result['message'])

        # If we're doing 10K/sec, it's OK.
        result = analyze_queue_stats('name', {'update_time': time.time(),
                                              'current_queue_size': 10000,
                                              'queue_last_emptied_timestamp': time.time() - 10000,
                                              'recent_average_consume_time': 0.0001}, 10000)
        self.assertEqual(result['status'], OK)

        # Verify logic around whether it'll take MAX_SECONDS_TO_CLEAR_NORMAL to clear queue.
        with mock.patch.dict('scripts.lib.check_rabbitmq_queue.MAX_SECONDS_TO_CLEAR_NORMAL',
                             {'name': 10}):
            result = analyze_queue_stats('name', {'update_time': time.time(),
                                                  'current_queue_size': 11,
                                                  'queue_last_emptied_timestamp': time.time() - 10000,
                                                  'recent_average_consume_time': 1}, 11)
            self.assertEqual(result['status'], WARNING)
            self.assertIn('clearing the backlog', result['message'])

            result = analyze_queue_stats('name', {'update_time': time.time(),
                                                  'current_queue_size': 9,
                                                  'queue_last_emptied_timestamp': time.time() - 10000,
                                                  'recent_average_consume_time': 1}, 9)
            self.assertEqual(result['status'], OK)

    def test_queue_burst(self) -> None:
        """Test logic for just after a large number of events were added
        to an empty queue.  Happens routinely for digest emails, for example."""
        result = analyze_queue_stats('name', {'update_time': time.time(),
                                              'current_queue_size': 10000,
                                              'queue_last_emptied_timestamp': time.time() - 1,
                                              'recent_average_consume_time': 1}, 10000)
        self.assertEqual(result['status'], CRITICAL)
        self.assertIn('clearing the burst', result['message'])

        # verify logic around MAX_SECONDS_TO_CLEAR_FOR_BURSTS.
        with mock.patch.dict('scripts.lib.check_rabbitmq_queue.MAX_SECONDS_TO_CLEAR_FOR_BURSTS',
                             {'name': 10}):
            result = analyze_queue_stats('name', {'update_time': time.time(),
                                                  'current_queue_size': 11,
                                                  'queue_last_emptied_timestamp': time.time() - 1,
                                                  'recent_average_consume_time': 1}, 11)
            self.assertEqual(result['status'], WARNING)
            self.assertIn('clearing the burst', result['message'])

            result = analyze_queue_stats('name', {'update_time': time.time(),
                                                  'current_queue_size': 9,
                                                  'queue_last_emptied_timestamp': time.time() - 1,
                                                  'recent_average_consume_time': 1}, 9)
            self.assertEqual(result['status'], OK)

    def test_queue_burst_long_time_to_clear_allowed(self) -> None:
        """
        For a queue that is allowed > 300s to clear a burst of events,
        we need to verify that the checker will not stop categorizing this as a burst
        while the worker is still processing the events, within the allowed time limit.
        """
        start_time = time.time()
        with mock.patch.dict('scripts.lib.check_rabbitmq_queue.CRITICAL_SECONDS_TO_CLEAR_FOR_BURSTS',
                             {'name': 600}), \
                mock.patch.dict('scripts.lib.check_rabbitmq_queue.MAX_SECONDS_TO_CLEAR_FOR_BURSTS',
                                {'name': 600}):
            with mock.patch('time.time', return_value=start_time + 599):
                result = analyze_queue_stats('name', {'update_time': time.time(),
                                                      'current_queue_size': 599,
                                                      'queue_last_emptied_timestamp': start_time,
                                                      'recent_average_consume_time': 1}, 599)
                self.assertEqual(result['status'], OK)

            with mock.patch('time.time', return_value=start_time + 601):
                result = analyze_queue_stats('name', {'update_time': time.time(),
                                                      'current_queue_size': 599,
                                                      'queue_last_emptied_timestamp': start_time,
                                                      'recent_average_consume_time': 1}, 599)
                self.assertEqual(result['status'], CRITICAL)
