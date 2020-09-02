import json
import os
import re
import subprocess
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

normal_queues = [
    'deferred_work',
    'digest_emails',
    'email_mirror',
    'embed_links',
    'embedded_bots',
    'error_reports',
    'invites',
    'email_senders',
    'missedmessage_emails',
    'missedmessage_mobile_notifications',
    'outgoing_webhooks',
    'signups',
    'user_activity',
    'user_activity_interval',
    'user_presence',
]

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

states = {
    0: "OK",
    1: "WARNING",
    2: "CRITICAL",
    3: "UNKNOWN",
}

MAX_SECONDS_TO_CLEAR_FOR_BURSTS: DefaultDict[str, int] = defaultdict(
    lambda: 120,
    digest_emails=600,
)
MAX_SECONDS_TO_CLEAR_NORMAL: DefaultDict[str, int] = defaultdict(
    lambda: 30,
    digest_emails=1200,
    missedmessage_mobile_notifications=120,
)
CRITICAL_SECONDS_TO_CLEAR_FOR_BURSTS: DefaultDict[str, int] = defaultdict(
    lambda: 240,
    digest_emails=1200,
)
CRITICAL_SECONDS_TO_CLEAR_NORMAL: DefaultDict[str, int] = defaultdict(
    lambda: 60,
    missedmessage_mobile_notifications=180,
    digest_emails=600,
)

def analyze_queue_stats(queue_name: str, stats: Dict[str, Any],
                        queue_count_rabbitmqctl: int) -> Dict[str, Any]:
    now = int(time.time())
    if stats == {}:
        return dict(status=UNKNOWN,
                    name=queue_name,
                    message='invalid or no stats data')

    if now - stats['update_time'] > 180 and queue_count_rabbitmqctl > 10:
        # Queue isn't updating the stats file and has some events in
        # the backlog, it's likely stuck.
        #
        # TODO: There's an unfortunate race where if the queue has
        # been empty for the last hour (because there haven't been 50
        # new events in the last hour), and then gets a burst, this
        # condition will be true for the first (event_handling_time *
        # 50).
        return dict(status=CRITICAL,
                    name=queue_name,
                    message='queue appears to be stuck, last update {}, queue size {}'.format(
                        stats['update_time'], queue_count_rabbitmqctl))

    current_size = stats['current_queue_size']
    average_consume_time = stats['recent_average_consume_time']
    if average_consume_time is None:
        # Queue just started; we can't effectively estimate anything.
        #
        # If the queue is stuck in this state and not processing
        # anything, eventually the `update_time` rule above will fire.
        return dict(status=OK,
                    name=queue_name,
                    message='')

    expected_time_to_clear_backlog = current_size * average_consume_time
    time_since_emptied = now - stats['queue_last_emptied_timestamp']
    if time_since_emptied > max(300, CRITICAL_SECONDS_TO_CLEAR_FOR_BURSTS[queue_name]):
        # We need the max() expression in case the rules for the queue
        # permit longer processing times than 300s - to prevent
        # incorrectly throwing an error by changing the classification
        # of the the backlog from "burst" to "not burst" after 300s,
        # while the worker is still processing it and staying below
        # the CRITICAL threshold.
        if expected_time_to_clear_backlog > MAX_SECONDS_TO_CLEAR_NORMAL[queue_name]:
            if expected_time_to_clear_backlog > CRITICAL_SECONDS_TO_CLEAR_NORMAL[queue_name]:
                status = CRITICAL
            else:
                status = WARNING

            return dict(status=status,
                        name=queue_name,
                        message=f'clearing the backlog will take too long: {expected_time_to_clear_backlog}s, size: {current_size}')
    else:
        # We slept recently, so treat this as a burst.
        if expected_time_to_clear_backlog > MAX_SECONDS_TO_CLEAR_FOR_BURSTS[queue_name]:
            if expected_time_to_clear_backlog > CRITICAL_SECONDS_TO_CLEAR_FOR_BURSTS[queue_name]:
                status = CRITICAL
            else:
                status = WARNING

            return dict(status=status,
                        name=queue_name,
                        message=f'clearing the burst will take too long: {expected_time_to_clear_backlog}s, size: {current_size}')

    return dict(status=OK,
                name=queue_name,
                message='')

WARN_COUNT_THRESHOLD_DEFAULT = 10
CRITICAL_COUNT_THRESHOLD_DEFAULT = 50
def check_other_queues(queue_counts_dict: Dict[str, int]) -> List[Dict[str, Any]]:
    """ Do a simple queue size check for queues whose workers don't publish stats files."""

    results = []
    for queue, count in queue_counts_dict.items():
        if queue in normal_queues:
            continue

        if count > CRITICAL_COUNT_THRESHOLD_DEFAULT:
            results.append(dict(status=CRITICAL, name=queue,
                                message=f'count critical: {count}'))
        elif count > WARN_COUNT_THRESHOLD_DEFAULT:
            results.append(dict(status=WARNING, name=queue,
                                message=f'count warning: {count}'))
        else:
            results.append(dict(status=OK, name=queue, message=''))

    return results

def check_rabbitmq_queues() -> None:
    pattern = re.compile(r'(\w+)\t(\d+)')
    if 'USER' in os.environ and not os.environ['USER'] in ['root', 'rabbitmq']:
        print("This script must be run as the root or rabbitmq user")

    list_queues_output = subprocess.check_output(['/usr/sbin/rabbitmqctl', 'list_queues'],
                                                 universal_newlines=True)
    list_consumers_output = subprocess.check_output(['/usr/sbin/rabbitmqctl', 'list_consumers'],
                                                    universal_newlines=True)

    queue_counts_rabbitmqctl = {}
    for line in list_queues_output.split("\n"):
        line = line.strip()
        m = pattern.match(line)
        if m:
            queue = m.group(1)
            count = int(m.group(2))
            queue_counts_rabbitmqctl[queue] = count

    queues_with_consumers = []
    for line in list_consumers_output.split('\n'):
        parts = line.split('\t')
        if len(parts) >= 2:
            queue_name = parts[0]
            if queue_name.startswith("notify_tornado"):
                continue
            queues_with_consumers.append(queue_name)

    queue_stats_dir = subprocess.check_output([os.path.join(ZULIP_PATH, 'scripts/get-django-setting'),
                                               'QUEUE_STATS_DIR'],
                                              universal_newlines=True).strip()
    queue_stats: Dict[str, Dict[str, Any]] = {}
    queues_to_check = set(normal_queues).intersection(set(queues_with_consumers))
    for queue in queues_to_check:
        fn = queue + ".stats"
        file_path = os.path.join(queue_stats_dir, fn)
        if not os.path.exists(file_path):
            queue_stats[queue] = {}
            continue

        with open(file_path) as f:
            try:
                queue_stats[queue] = json.load(f)
            except json.decoder.JSONDecodeError:
                queue_stats[queue] = {}

    results = []
    for queue_name, stats in queue_stats.items():
        results.append(analyze_queue_stats(queue_name, stats, queue_counts_rabbitmqctl[queue_name]))

    results.extend(check_other_queues(queue_counts_rabbitmqctl))

    status = max(result['status'] for result in results)

    now = int(time.time())

    if status > 0:
        queue_error_template = "queue {} problem: {}:{}"
        error_message = '; '.join(
            queue_error_template.format(result['name'], states[result['status']], result['message'])
            for result in results if result['status'] > 0
        )
        print(f"{now}|{status}|{states[status]}|{error_message}")
    else:
        print(f"{now}|{status}|{states[status]}|queues normal")
