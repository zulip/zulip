import json
import os
import re
import subprocess
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

normal_queues = [
    "deferred_work",
    "digest_emails",
    "email_mirror",
    "embed_links",
    "embedded_bots",
    "error_reports",
    "invites",
    "email_senders",
    "missedmessage_emails",
    "missedmessage_mobile_notifications",
    "outgoing_webhooks",
    "user_activity",
    "user_activity_interval",
    "user_presence",
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

MAX_SECONDS_TO_CLEAR: DefaultDict[str, int] = defaultdict(
    lambda: 30,
    digest_emails=1200,
    missedmessage_mobile_notifications=120,
    embed_links=60,
)
CRITICAL_SECONDS_TO_CLEAR: DefaultDict[str, int] = defaultdict(
    lambda: 60,
    missedmessage_mobile_notifications=180,
    digest_emails=1800,
    embed_links=90,
)


def analyze_queue_stats(
    queue_name: str, stats: Dict[str, Any], old_stats: Dict[str, Any], queue_count_rabbitmqctl: int
) -> Dict[str, Any]:
    now = int(time.time())
    if stats == {}:
        return dict(status=UNKNOWN, name=queue_name, message="invalid or no stats data")

    if now - stats["update_time"] > 180 and queue_count_rabbitmqctl > 10:
        # Queue isn't updating the stats file and has some events in
        # the backlog, it's likely stuck.
        #
        # TODO: There's an unlikely race condition here - if the queue
        # was fully emptied and was idle due to no new events coming
        # for over 180 seconds, suddenly gets a burst of events and
        # this code runs exactly in the very small time window between
        # those events popping up and the queue beginning to process
        # the first one (which will refresh the stats file at the very
        # start), we'll incorrectly return the CRITICAL status. The
        # chance of that happening should be negligible because the queue
        # worker should wake up immediately and log statistics before
        # starting to process the first event.
        return dict(
            status=CRITICAL,
            name=queue_name,
            message="queue appears to be stuck, last update {}, queue size {}".format(
                stats["update_time"], queue_count_rabbitmqctl
            ),
        )

    if (
        old_stats
        and now - stats["update_time"] <= 180
        and stats["recent_average_consume_time"] is None
        and now - old_stats["update_time"] > 180
        and queue_count_rabbitmqctl > 10
    ):
        # It's likely the worker keeps restarting and isn't processing events.
        # This will trigger a false alarm if a worker is started after >180s of downtime and
        # there is a number of events in the queue - and will resolve after a while once the
        # worker has calculated its average consume time and updated the stats. That should be okay
        # because restarting after significant downtime means something attention-worthy was
        # happening anyway and it's likely other alerts will be triggered due to the accumulated
        # backlog.
        return dict(
            status=CRITICAL,
            name=queue_name,
            message="queue may be continually restarting, last update {}, queue size {} old stats file last update {}".format(
                stats["update_time"], queue_count_rabbitmqctl, old_stats["update_time"]
            ),
        )

    current_size = queue_count_rabbitmqctl
    average_consume_time = stats["recent_average_consume_time"]
    if average_consume_time is None:
        # Queue just started; we can't effectively estimate anything.
        #
        # If the queue is stuck in this state and not processing
        # anything, eventually the `update_time` rule above will fire.
        return dict(status=OK, name=queue_name, message="")

    expected_time_to_clear_backlog = current_size * average_consume_time
    if expected_time_to_clear_backlog > MAX_SECONDS_TO_CLEAR[queue_name]:
        if expected_time_to_clear_backlog > CRITICAL_SECONDS_TO_CLEAR[queue_name]:
            status = CRITICAL
        else:
            status = WARNING

        return dict(
            status=status,
            name=queue_name,
            message=f"clearing the backlog will take too long: {expected_time_to_clear_backlog}s, size: {current_size}",
        )

    return dict(status=OK, name=queue_name, message="")


WARN_COUNT_THRESHOLD_DEFAULT = 10
CRITICAL_COUNT_THRESHOLD_DEFAULT = 50


def check_other_queues(queue_counts_dict: Dict[str, int]) -> List[Dict[str, Any]]:
    """Do a simple queue size check for queues whose workers don't publish stats files."""

    results = []
    for queue, count in queue_counts_dict.items():
        if queue in normal_queues:
            continue

        if count > CRITICAL_COUNT_THRESHOLD_DEFAULT:
            results.append(dict(status=CRITICAL, name=queue, message=f"count critical: {count}"))
        elif count > WARN_COUNT_THRESHOLD_DEFAULT:
            results.append(dict(status=WARNING, name=queue, message=f"count warning: {count}"))
        else:
            results.append(dict(status=OK, name=queue, message=""))

    return results


def check_rabbitmq_queues() -> None:
    pattern = re.compile(r"(\w+)\t(\d+)\t(\d+)")
    if "USER" in os.environ and not os.environ["USER"] in ["root", "rabbitmq"]:
        print("This script must be run as the root or rabbitmq user")

    list_queues_output = subprocess.check_output(
        ["/usr/sbin/rabbitmqctl", "list_queues", "name", "messages", "consumers"],
        universal_newlines=True,
    )
    queue_counts_rabbitmqctl = {}
    queues_with_consumers = []
    for line in list_queues_output.split("\n"):
        line = line.strip()
        m = pattern.match(line)
        if m:
            queue = m.group(1)
            count = int(m.group(2))
            consumers = int(m.group(3))
            queue_counts_rabbitmqctl[queue] = count
            if consumers > 0 and not queue.startswith("notify_tornado"):
                queues_with_consumers.append(queue)

    queue_stats_dir = subprocess.check_output(
        [os.path.join(ZULIP_PATH, "scripts/get-django-setting"), "QUEUE_STATS_DIR"],
        universal_newlines=True,
    ).strip()
    queue_stats: Dict[str, Dict[str, Any]] = {}
    old_queue_stats: Dict[str, Dict[str, Any]] = {}
    queues_to_check = set(normal_queues).intersection(set(queues_with_consumers))
    for queue in queues_to_check:
        fn = queue + ".stats"
        file_path = os.path.join(queue_stats_dir, fn)
        old_file_path = file_path + ".old"

        queue_stats[queue] = get_data_from_file(file_path)
        old_queue_stats[queue] = get_data_from_file(old_file_path)

    results = []
    for queue_name, stats in queue_stats.items():
        results.append(
            analyze_queue_stats(
                queue_name, stats, old_queue_stats[queue_name], queue_counts_rabbitmqctl[queue_name]
            )
        )

    results.extend(check_other_queues(queue_counts_rabbitmqctl))

    status = max(result["status"] for result in results)

    now = int(time.time())

    if status > 0:
        queue_error_template = "queue {} problem: {}:{}"
        error_message = "; ".join(
            queue_error_template.format(result["name"], states[result["status"]], result["message"])
            for result in results
            if result["status"] > 0
        )
        print(f"{now}|{status}|{states[status]}|{error_message}")
    else:
        print(f"{now}|{status}|{states[status]}|queues normal")


def get_data_from_file(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {}

    with open(file_path) as f:
        try:
            return json.load(f)
        except json.decoder.JSONDecodeError:
            return {}
