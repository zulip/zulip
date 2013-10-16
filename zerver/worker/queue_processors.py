from __future__ import absolute_import

from django.db.transaction import commit_on_success
from django.conf import settings
from postmonkey import PostMonkey, MailChimpException
from zerver.models import UserActivityInterval, get_user_profile_by_email, \
    get_user_profile_by_id, get_prereg_user_by_email, get_client
from zerver.lib.queue import SimpleQueueClient
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.actions import handle_missedmessage_emails, do_send_confirmation_email, \
    do_update_user_activity, do_update_user_activity_interval, do_update_user_presence, \
    internal_send_message, send_local_email_template_with_delay
from zerver.decorator import JsonableError
import os
import ujson
import traceback
from collections import defaultdict
import time
import datetime
import logging

def assign_queue(queue_name):
    def decorate(clazz):
        clazz.queue_name = queue_name
        register_worker(queue_name, clazz)
        return clazz
    return decorate

worker_classes = {}
def register_worker(queue_name, clazz):
    worker_classes[queue_name] = clazz

def get_worker(queue_name):
    return worker_classes[queue_name]()

class QueueProcessingWorker(object):
    def __init__(self):
        self.q = SimpleQueueClient()

    def start(self):
        self.q.register_json_consumer(self.queue_name, self.consume)
        self.q.start_consuming()

    def stop(self):
        self.q.stop_consuming()

@assign_queue('signups')
class SignupWorker(QueueProcessingWorker):
    def __init__(self):
        super(SignupWorker, self).__init__()
        self.pm = PostMonkey(settings.MAILCHIMP_API_KEY, timeout=10)

    # Changes to this should also be reflected in
    # zerver/management/commands/queue_followup_emails.py:queue()
    def consume(self, ch, method, properties, data):
        merge_vars=data['merge_vars']
        try:
            self.pm.listSubscribe(
                    id=settings.ZULIP_FRIENDS_LIST_ID,
                    email_address=data['EMAIL'],
                    merge_vars=merge_vars,
                    double_optin=False,
                    send_welcome=False)
        except MailChimpException, e:
            if e.code == 214:
                logging.warning("Attempted to sign up already existing email to list: %s" % (data['EMAIL'],))
            else:
                raise e

        email = data.get("EMAIL")
        name = merge_vars.get("NAME")
        #Send day 1 email
        send_local_email_template_with_delay([{'email': email, 'name': name}],
                                             "zerver/emails/followup/day1",
                                             {'name': name},
                                             datetime.timedelta(hours=1),
                                             tags=["followup-emails"],
                                             sender={'email': 'wdaher@zulip.com', 'name': 'Waseem Daher'})
        #Send day 2 email
        tomorrow = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        # 11 AM EDT
        tomorrow_morning = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 15, 0)
        assert(datetime.datetime.utcnow() < tomorrow_morning)
        send_local_email_template_with_delay([{'email': email, 'name': name}],
                                             "zerver/emails/followup/day2",
                                             {'name': name},
                                             tomorrow_morning - datetime.datetime.utcnow(),
                                             tags=["followup-emails"],
                                             sender={'email': 'wdaher@zulip.com', 'name': 'Waseem Daher'})

@assign_queue('invites')
class ConfirmationEmailWorker(QueueProcessingWorker):
    def consume(self, ch, method, properties, data):
        invitee = get_prereg_user_by_email(data["email"])
        referrer = get_user_profile_by_email(data["referrer_email"])
        do_send_confirmation_email(invitee, referrer)

@assign_queue('user_activity')
class UserActivityWorker(QueueProcessingWorker):
    def consume(self, ch, method, properties, event):
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        query = event["query"]
        do_update_user_activity(user_profile, client, query, log_time)

@assign_queue('user_activity_interval')
class UserActivityIntervalWorker(QueueProcessingWorker):
    def consume(self, ch, method, properties, event):
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        log_time = timestamp_to_datetime(event["time"])
        do_update_user_activity_interval(user_profile, log_time)

@assign_queue('user_presence')
class UserPresenceWorker(QueueProcessingWorker):
    def consume(self, ch, method, properties, event):
        logging.info("Received event: %s" % (event),)
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        status = event["status"]
        do_update_user_presence(user_profile, client, log_time, status)

@assign_queue('missedmessage_emails')
class MissedMessageWorker(QueueProcessingWorker):
    def start(self):
        while True:
            missed_events = self.q.drain_queue("missedmessage_emails", json=True)
            by_recipient = defaultdict(list)

            for event in missed_events:
                logging.info("Received event: %s" % (event,))
                by_recipient[event['user_profile_id']].append(event)

            for user_profile_id, events in by_recipient.items():
                handle_missedmessage_emails(user_profile_id, events)

            # Aggregate all messages received every 2 minutes to let someone finish sending a batch
            # of messages
            time.sleep(2 * 60)

@assign_queue('slow_queries')
class SlowQueryWorker(QueueProcessingWorker):
    def start(self):
        while True:
            slow_queries = self.q.drain_queue("slow_queries", json=True)

            if len(slow_queries) > 0:
                topic = "%s: slow queries" % (settings.STATSD_PREFIX,)

                content = ""
                for query in slow_queries:
                    content += "    %s\n" % (query,)

                with commit_on_success():
                    internal_send_message("error-bot@zulip.com", "stream", "logs", topic, content)

            # Aggregate all slow query messages in 1-minute chunks to avoid message spam
            time.sleep(1 * 60)
