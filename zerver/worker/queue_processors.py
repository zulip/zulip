# Documented in http://zulip.readthedocs.io/en/latest/queuing.html
from __future__ import absolute_import
from typing import Any, Callable, Dict, List, Mapping, Optional, cast

import signal
import sys
import os

from zulip_bots.lib import ExternalBotHandler, StateHandler
from django.conf import settings
from django.db import connection
from django.core.handlers.wsgi import WSGIRequest
from django.core.handlers.base import BaseHandler
from zerver.models import \
    get_client, get_prereg_user_by_email, get_system_bot, ScheduledEmail, \
    get_user_profile_by_id, Message, Realm, Service, UserMessage, UserProfile
from zerver.lib.context_managers import lockfile
from zerver.lib.error_notify import do_report_error
from zerver.lib.feedback import handle_feedback
from zerver.lib.queue import SimpleQueueClient, queue_json_publish
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.notifications import handle_missedmessage_emails, enqueue_welcome_emails
from zerver.lib.push_notifications import handle_push_notification
from zerver.lib.actions import do_send_confirmation_email, \
    do_update_user_activity, do_update_user_activity_interval, do_update_user_presence, \
    internal_send_message, check_send_message, extract_recipients, \
    render_incoming_message, do_update_embedded_data
from zerver.lib.url_preview import preview as url_preview
from zerver.lib.digest import handle_digest_email
from zerver.lib.send_email import send_future_email, send_email_from_dict, \
    FromAddress, EmailNotDeliveredException
from zerver.lib.email_mirror import process_message as mirror_email
from zerver.decorator import JsonableError
from zerver.tornado.socket import req_redis_key
from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.db import reset_queries
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.str_utils import force_str
from zerver.context_processors import common_context
from zerver.lib.outgoing_webhook import do_rest_call, get_outgoing_webhook_service_handler
from zerver.models import get_bot_services
from zulip import Client
from zerver.lib.bot_lib import EmbeddedBotHandler, get_bot_handler

import os
import sys
import six
import ujson
from collections import defaultdict
import email
import time
import datetime
import logging
import requests
import simplejson
from six.moves import cStringIO as StringIO
import re
import importlib


class WorkerDeclarationException(Exception):
    pass

def assign_queue(queue_name, enabled=True, queue_type="consumer"):
    # type: (str, bool, str) -> Callable[[QueueProcessingWorker], QueueProcessingWorker]
    def decorate(clazz):
        # type: (QueueProcessingWorker) -> QueueProcessingWorker
        clazz.queue_name = queue_name
        if enabled:
            register_worker(queue_name, clazz, queue_type)
        return clazz
    return decorate

worker_classes = {}  # type: Dict[str, Any] # Any here should be QueueProcessingWorker type
queues = {}  # type: Dict[str, Dict[str, QueueProcessingWorker]]
def register_worker(queue_name, clazz, queue_type):
    # type: (str, QueueProcessingWorker, str) -> None
    if queue_type not in queues:
        queues[queue_type] = {}
    queues[queue_type][queue_name] = clazz
    worker_classes[queue_name] = clazz

def get_worker(queue_name):
    # type: (str) -> QueueProcessingWorker
    return worker_classes[queue_name]()

def get_active_worker_queues(queue_type=None):
    # type: (Optional[str]) -> List[str]
    """Returns all the non-test worker queues."""
    if queue_type is None:
        return list(worker_classes.keys())
    return list(queues[queue_type].keys())

def check_and_send_restart_signal():
    # type: () -> None
    try:
        if not connection.is_usable():
            logging.warning("*** Sending self SIGUSR1 to trigger a restart.")
            os.kill(os.getpid(), signal.SIGUSR1)
    except Exception:
        pass

class QueueProcessingWorker(object):
    queue_name = None  # type: str

    def __init__(self):
        # type: () -> None
        self.q = None  # type: SimpleQueueClient
        if self.queue_name is None:
            raise WorkerDeclarationException("Queue worker declared without queue_name")

    def consume(self, data):
        # type: (Mapping[str, Any]) -> None
        raise WorkerDeclarationException("No consumer defined!")

    def consume_wrapper(self, data):
        # type: (Mapping[str, Any]) -> None
        try:
            self.consume(data)
        except Exception:
            self._log_problem()
            if not os.path.exists(settings.QUEUE_ERROR_DIR):
                os.mkdir(settings.QUEUE_ERROR_DIR)
            fname = '%s.errors' % (self.queue_name,)
            fn = os.path.join(settings.QUEUE_ERROR_DIR, fname)
            line = u'%s\t%s\n' % (time.asctime(), ujson.dumps(data))
            lock_fn = fn + '.lock'
            with lockfile(lock_fn):
                with open(fn, 'ab') as f:
                    f.write(line.encode('utf-8'))
            check_and_send_restart_signal()
        finally:
            reset_queries()

    def _log_problem(self):
        # type: () -> None
        logging.exception("Problem handling data on queue %s" % (self.queue_name,))

    def setup(self):
        # type: () -> None
        self.q = SimpleQueueClient()

    def start(self):
        # type: () -> None
        self.q.register_json_consumer(self.queue_name, self.consume_wrapper)
        self.q.start_consuming()

    def stop(self):
        # type: () -> None
        self.q.stop_consuming()

@assign_queue('signups')
class SignupWorker(QueueProcessingWorker):
    def consume(self, data):
        # type: (Mapping[str, Any]) -> None
        user_profile = get_user_profile_by_id(data['user_id'])
        logging.info("Processing signup for user %s in realm %s" % (
            user_profile.email, user_profile.realm.string_id))
        if settings.MAILCHIMP_API_KEY and settings.PRODUCTION:
            endpoint = "https://%s.api.mailchimp.com/3.0/lists/%s/members" % \
                       (settings.MAILCHIMP_API_KEY.split('-')[1], settings.ZULIP_FRIENDS_LIST_ID)
            params = dict(data)
            del params['user_id']
            params['list_id'] = settings.ZULIP_FRIENDS_LIST_ID
            params['status'] = 'subscribed'
            r = requests.post(endpoint, auth=('apikey', settings.MAILCHIMP_API_KEY), json=params, timeout=10)
            if r.status_code == 400 and ujson.loads(r.text)['title'] == 'Member Exists':
                logging.warning("Attempted to sign up already existing email to list: %s" %
                                (data['email_address'],))
            else:
                r.raise_for_status()

@assign_queue('invites')
class ConfirmationEmailWorker(QueueProcessingWorker):
    def consume(self, data):
        # type: (Mapping[str, Any]) -> None
        invitee = get_prereg_user_by_email(data["email"])
        referrer = get_user_profile_by_id(data["referrer_id"])
        body = data["email_body"]
        logging.info("Sending invitation for realm %s to %s" % (referrer.realm.string_id, invitee.email))
        do_send_confirmation_email(invitee, referrer, body)

        # queue invitation reminder for two days from now.
        link = create_confirmation_link(invitee, referrer.realm.host, Confirmation.INVITATION)
        context = common_context(referrer)
        context.update({
            'activate_url': link,
            'referrer_name': referrer.full_name,
            'referrer_email': referrer.email,
            'referrer_realm_name': referrer.realm.name,
        })
        send_future_email(
            "zerver/emails/invitation_reminder",
            to_email=data["email"],
            from_address=FromAddress.NOREPLY,
            context=context,
            delay=datetime.timedelta(days=2))

@assign_queue('user_activity')
class UserActivityWorker(QueueProcessingWorker):
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        query = event["query"]
        do_update_user_activity(user_profile, client, query, log_time)

@assign_queue('user_activity_interval')
class UserActivityIntervalWorker(QueueProcessingWorker):
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        log_time = timestamp_to_datetime(event["time"])
        do_update_user_activity_interval(user_profile, log_time)

@assign_queue('user_presence')
class UserPresenceWorker(QueueProcessingWorker):
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        logging.info("Received event: %s" % (event),)
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        status = event["status"]
        do_update_user_presence(user_profile, client, log_time, status)

@assign_queue('missedmessage_emails', queue_type="loop")
class MissedMessageWorker(QueueProcessingWorker):
    def start(self):
        # type: () -> None
        while True:
            missed_events = self.q.drain_queue("missedmessage_emails", json=True)
            by_recipient = defaultdict(list)  # type: Dict[int, List[Dict[str, Any]]]

            for event in missed_events:
                logging.info("Received event: %s" % (event,))
                by_recipient[event['user_profile_id']].append(event)

            for user_profile_id, events in by_recipient.items():
                handle_missedmessage_emails(user_profile_id, events)

            reset_queries()
            # Aggregate all messages received every 2 minutes to let someone finish sending a batch
            # of messages
            time.sleep(2 * 60)

@assign_queue('missedmessage_email_senders')
class MissedMessageSendingWorker(QueueProcessingWorker):
    def consume(self, data):
        # type: (Mapping[str, Any]) -> None
        try:
            send_email_from_dict(data)
        except EmailNotDeliveredException:
            # TODO: Do something smarter here ..
            pass

@assign_queue('missedmessage_mobile_notifications')
class PushNotificationsWorker(QueueProcessingWorker):
    def consume(self, data):
        # type: (Mapping[str, Any]) -> None
        handle_push_notification(data['user_profile_id'], data)

def make_feedback_client():
    # type: () -> Any # Should be zulip.Client, but not necessarily importable
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../api'))
    import zulip
    return zulip.Client(
        client="ZulipFeedback/0.1",
        email=settings.DEPLOYMENT_ROLE_NAME,
        api_key=settings.DEPLOYMENT_ROLE_KEY,
        verbose=True,
        site=settings.FEEDBACK_TARGET)

# We probably could stop running this queue worker at all if ENABLE_FEEDBACK is False
@assign_queue('feedback_messages')
class FeedbackBot(QueueProcessingWorker):
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        logging.info("Received feedback from %s" % (event["sender_email"],))
        handle_feedback(event)

@assign_queue('error_reports')
class ErrorReporter(QueueProcessingWorker):
    def start(self):
        # type: () -> None
        if settings.DEPLOYMENT_ROLE_KEY:
            self.staging_client = make_feedback_client()
            self.staging_client._register(
                'forward_error',
                method='POST',
                url='deployments/report_error',
                make_request=(lambda type, report: {'type': type, 'report': simplejson.dumps(report)}),
            )
        QueueProcessingWorker.start(self)

    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        logging.info("Processing traceback with type %s for %s" % (event['type'], event.get('user_email')))
        if settings.DEPLOYMENT_ROLE_KEY:
            self.staging_client.forward_error(event['type'], event['report'])
        elif settings.ERROR_REPORTING:
            do_report_error(event['report']['host'], event['type'], event['report'])

@assign_queue('slow_queries', queue_type="loop")
class SlowQueryWorker(QueueProcessingWorker):
    def start(self):
        # type: () -> None
        while True:
            self.process_one_batch()
            # Aggregate all slow query messages in 1-minute chunks to avoid message spam
            time.sleep(1 * 60)

    def process_one_batch(self):
        # type: () -> None
        slow_queries = self.q.drain_queue("slow_queries", json=True)

        for query in slow_queries:
            logging.info("Slow query: %s" % (query))

        if settings.ERROR_BOT is None:
            return

        if len(slow_queries) > 0:
            topic = "%s: slow queries" % (settings.EXTERNAL_HOST,)

            content = ""
            for query in slow_queries:
                content += "    %s\n" % (query,)

            error_bot_realm = get_system_bot(settings.ERROR_BOT).realm
            internal_send_message(error_bot_realm, settings.ERROR_BOT,
                                  "stream", "logs", topic, content)

        reset_queries()

@assign_queue("message_sender")
class MessageSenderWorker(QueueProcessingWorker):
    def __init__(self):
        # type: () -> None
        super(MessageSenderWorker, self).__init__()
        self.redis_client = get_redis_client()
        self.handler = BaseHandler()
        self.handler.load_middleware()

    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        server_meta = event['server_meta']

        environ = {
            'REQUEST_METHOD': 'SOCKET',
            'SCRIPT_NAME': '',
            'PATH_INFO': '/json/messages',
            'SERVER_NAME': '127.0.0.1',
            'SERVER_PORT': 9993,
            'SERVER_PROTOCOL': 'ZULIP_SOCKET/1.0',
            'wsgi.version': (1, 0),
            'wsgi.input': StringIO(),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'zulip.emulated_method': 'POST'
        }

        if 'socket_user_agent' in event['request']:
            environ['HTTP_USER_AGENT'] = event['request']['socket_user_agent']
            del event['request']['socket_user_agent']

        # We're mostly using a WSGIRequest for convenience
        environ.update(server_meta['request_environ'])
        request = WSGIRequest(environ)
        # Note: If we ever support non-POST methods, we'll need to change this.
        request._post = event['request']
        request.csrf_processing_done = True

        user_profile = get_user_profile_by_id(server_meta['user_id'])
        request._cached_user = user_profile

        resp = self.handler.get_response(request)
        server_meta['time_request_finished'] = time.time()
        server_meta['worker_log_data'] = request._log_data

        resp_content = resp.content.decode('utf-8')
        response_data = ujson.loads(resp_content)
        if response_data['result'] == 'error':
            check_and_send_restart_signal()

        result = {'response': response_data, 'req_id': event['req_id'],
                  'server_meta': server_meta}

        redis_key = req_redis_key(event['req_id'])
        self.redis_client.hmset(redis_key, {'status': 'complete',
                                            'response': resp_content})

        queue_json_publish(server_meta['return_queue'], result, lambda e: None)

@assign_queue('digest_emails')
class DigestWorker(QueueProcessingWorker):
    # Who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        logging.info("Received digest event: %s" % (event,))
        handle_digest_email(event["user_profile_id"], event["cutoff"])

@assign_queue('email_mirror')
class MirrorWorker(QueueProcessingWorker):
    # who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        message = force_str(event["message"])
        mirror_email(email.message_from_string(message),
                     rcpt_to=event["rcpt_to"], pre_checked=True)

@assign_queue('test', queue_type="test")
class TestWorker(QueueProcessingWorker):
    # This worker allows you to test the queue worker infrastructure without
    # creating significant side effects.  It can be useful in development or
    # for troubleshooting prod/staging.  It pulls a message off the test queue
    # and appends it to a file in /tmp.
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        fn = settings.ZULIP_WORKER_TEST_FILE
        message = ujson.dumps(event)
        logging.info("TestWorker should append this message to %s: %s" % (fn, message))
        with open(fn, 'a') as f:
            f.write(message + '\n')

@assign_queue('embed_links')
class FetchLinksEmbedData(QueueProcessingWorker):
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        for url in event['urls']:
            url_preview.get_link_embed_data(url)

        message = Message.objects.get(id=event['message_id'])
        # If the message changed, we will run this task after updating the message
        # in zerver.views.messages.update_message_backend
        if message.content != event['message_content']:
            return
        if message.content is not None:
            query = UserMessage.objects.filter(
                message=message.id
            )
            message_user_ids = set(query.values_list('user_profile_id', flat=True))

            # Fetch the realm whose settings we're using for rendering
            realm = Realm.objects.get(id=event['message_realm_id'])

            # If rendering fails, the called code will raise a JsonableError.
            rendered_content = render_incoming_message(
                message,
                message.content,
                message_user_ids,
                realm)
            do_update_embedded_data(
                message.sender, message, message.content, rendered_content)

@assign_queue('outgoing_webhooks')
class OutgoingWebhookWorker(QueueProcessingWorker):
    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        message = event['message']
        dup_event = cast(Dict[str, Any], event)
        dup_event['command'] = message['content']

        services = get_bot_services(event['user_profile_id'])
        for service in services:
            dup_event['service_name'] = str(service.name)
            service_handler = get_outgoing_webhook_service_handler(service)
            rest_operation, request_data = service_handler.process_event(dup_event)
            do_rest_call(rest_operation, request_data, dup_event, service_handler)

@assign_queue('embedded_bots')
class EmbeddedBotWorker(QueueProcessingWorker):

    def get_bot_api_client(self, user_profile):
        # type: (UserProfile) -> EmbeddedBotHandler
        return EmbeddedBotHandler(user_profile)

    # TODO: Handle stateful bots properly
    def get_state_handler(self):
        # type: () -> StateHandler
        return StateHandler()

    def consume(self, event):
        # type: (Mapping[str, Any]) -> None
        user_profile_id = event['user_profile_id']
        user_profile = get_user_profile_by_id(user_profile_id)

        message = cast(Dict[str, Any], event['message'])

        # TODO: Do we actually want to allow multiple Services per bot user?
        services = get_bot_services(user_profile_id)
        for service in services:
            bot_handler = get_bot_handler(str(service.name))
            if bot_handler is None:
                logging.error("Error: User %s has bot with invalid embedded bot service %s" % (user_profile_id, service.name))
                continue
            bot_handler.handle_message(
                message=message,
                bot_handler=self.get_bot_api_client(user_profile),
                state_handler=self.get_state_handler())
