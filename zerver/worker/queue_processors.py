from __future__ import absolute_import

from django.conf import settings
from postmonkey import PostMonkey, MailChimpException
from zerver.models import get_user_profile_by_email, get_prereg_user_by_email
from zerver.lib.queue import SimpleQueueClient
from zerver.lib.actions import handle_missedmessage_emails, process_user_activity_event, \
    process_user_presence_event, process_user_activity_interval_event, do_send_confirmation_email
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

    def consume(self, ch, method, properties, data):
        try:
            self.pm.listSubscribe(
                    id=settings.ZULIP_FRIENDS_LIST_ID,
                    email_address=data['EMAIL'],
                    merge_vars=data['merge_vars'],
                    double_optin=False,
                    send_welcome=False)
        except MailChimpException, e:
            if e.code == 214:
                logging.warning("Attempted to sign up already existing email to list: %s" % (data['EMAIL'],))
            else:
                raise e

@assign_queue('invites')
class ConfirmationEmailWorker(QueueProcessingWorker):
    def consume(self, ch, method, properties, data):
        invitee = get_prereg_user_by_email(data["email"])
        referrer = get_user_profile_by_email(data["referrer_email"])
        do_send_confirmation_email(invitee, referrer)

@assign_queue('user_activity')
class UserActivityWorker(QueueProcessingWorker):
    ERROR_LOG_FILE = os.path.join(settings.ERROR_LOG_DIR, "process_user_activity")
    def consume(self, ch, method, properties, event):
        print " [x] Received activity %r" % (event,)
        try:
            self.process_event(event)
        except Exception:
            if not os.path.exists(settings.ERROR_LOG_DIR):
                os.mkdir(settings.ERROR_LOG_DIR)
            # One can parse out just the JSON records from this log format using:
            #
            # grep "Error Processing" errors/process_user_activity  | cut -f 2- -d:
            file(self.ERROR_LOG_FILE, "a").write(
                "Error Processing event: " + ujson.dumps(event) + "\n" +
                traceback.format_exc())

    def process_event(self, event):
        msg_type = event['type']
        if msg_type == 'user_activity':
            process_user_activity_event(event)
        elif msg_type == 'user_presence':
            process_user_presence_event(event)
        elif msg_type == 'user_activity_interval':
            process_user_activity_interval_event(event)
        else:
            print("[*] Unknown message type: %s" % (msg_type,))

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
