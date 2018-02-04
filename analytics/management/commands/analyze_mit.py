import datetime
import logging
import time
from typing import Any, Dict

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models import Message, Recipient

def compute_stats(log_level: int) -> None:
    logger = logging.getLogger()
    logger.setLevel(log_level)

    one_week_ago = timestamp_to_datetime(time.time()) - datetime.timedelta(weeks=1)
    mit_query = Message.objects.filter(sender__realm__string_id="zephyr",
                                       recipient__type=Recipient.STREAM,
                                       pub_date__gt=one_week_ago)
    for bot_sender_start in ["imap.", "rcmd.", "sys."]:
        mit_query = mit_query.exclude(sender__email__startswith=(bot_sender_start))
    # Filtering for "/" covers tabbott/extra@ and all the daemon/foo bots.
    mit_query = mit_query.exclude(sender__email__contains=("/"))
    mit_query = mit_query.exclude(sender__email__contains=("aim.com"))
    mit_query = mit_query.exclude(
        sender__email__in=["rss@mit.edu", "bash@mit.edu", "apache@mit.edu",
                           "bitcoin@mit.edu", "lp@mit.edu", "clocks@mit.edu",
                           "root@mit.edu", "nagios@mit.edu",
                           "www-data|local-realm@mit.edu"])
    user_counts = {}  # type: Dict[str, Dict[str, int]]
    for m in mit_query.select_related("sending_client", "sender"):
        email = m.sender.email
        user_counts.setdefault(email, {})
        user_counts[email].setdefault(m.sending_client.name, 0)
        user_counts[email][m.sending_client.name] += 1

    total_counts = {}  # type: Dict[str, int]
    total_user_counts = {}  # type: Dict[str, int]
    for email, counts in user_counts.items():
        total_user_counts.setdefault(email, 0)
        for client_name, count in counts.items():
            total_counts.setdefault(client_name, 0)
            total_counts[client_name] += count
            total_user_counts[email] += count

    logging.debug("%40s | %10s | %s" % ("User", "Messages", "Percentage Zulip"))
    top_percents = {}  # type: Dict[int, float]
    for size in [10, 25, 50, 100, 200, len(total_user_counts.keys())]:
        top_percents[size] = 0.0
    for i, email in enumerate(sorted(total_user_counts.keys(),
                                     key=lambda x: -total_user_counts[x])):
        percent_zulip = round(100 - (user_counts[email].get("zephyr_mirror", 0)) * 100. /
                              total_user_counts[email], 1)
        for size in top_percents.keys():
            top_percents.setdefault(size, 0)
            if i < size:
                top_percents[size] += (percent_zulip * 1.0 / size)

        logging.debug("%40s | %10s | %s%%" % (email, total_user_counts[email],
                                              percent_zulip))

    logging.info("")
    for size in sorted(top_percents.keys()):
        logging.info("Top %6s | %s%%" % (size, round(top_percents[size], 1)))

    grand_total = sum(total_counts.values())
    print(grand_total)
    logging.info("%15s | %s" % ("Client", "Percentage"))
    for client in total_counts.keys():
        logging.info("%15s | %s%%" % (client, round(100. * total_counts[client] / grand_total, 1)))

class Command(BaseCommand):
    help = "Compute statistics on MIT Zephyr usage."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--verbose', default=False, action='store_true')

    def handle(self, *args: Any, **options: Any) -> None:
        level = logging.INFO
        if options["verbose"]:
            level = logging.DEBUG
        compute_stats(level)
