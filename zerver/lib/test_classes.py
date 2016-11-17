from __future__ import absolute_import
from __future__ import print_function
from contextlib import contextmanager
from typing import (cast, Any, Callable, Dict, Generator, Iterable, List, Mapping, Optional,
    Sized, Tuple, Union)

from django.core.urlresolvers import resolve
from django.conf import settings
from django.test import TestCase
from django.test.client import (
    BOUNDARY, MULTIPART_CONTENT, encode_multipart,
)
from django.template import loader
from django.http import HttpResponse
from django.db.utils import IntegrityError
from django.utils.translation import ugettext as _

from zerver.lib.initial_password import initial_password
from zerver.lib.db import TimeTrackingCursor
from zerver.lib.handlers import allocate_handler_id
from zerver.lib.str_utils import force_text
from zerver.lib import cache
from zerver.lib import event_queue
from zerver.worker import queue_processors

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, bulk_add_subscriptions,
    get_display_recipient, bulk_remove_subscriptions
)

from zerver.lib.test_helpers import (
    instrument_url, find_key_by_email,
)

from zerver.models import (
    get_realm,
    get_stream,
    get_user_profile_by_email,
    get_realm_by_email_domain,
    Client,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)

from zerver.lib.request import JsonableError


import base64
import mock
import os
import re
import time
import ujson
import unittest
from six.moves import urllib
from six import text_type, binary_type
from zerver.lib.str_utils import NonBinaryStr

from contextlib import contextmanager
import six

API_KEYS = {} # type: Dict[text_type, text_type]

skip_py3 = unittest.skipIf(six.PY3, "Expected failure on Python 3")



class ZulipTestCase(TestCase):
    '''
    WRAPPER_COMMENT:

    We wrap calls to self.client.{patch,put,get,post,delete} for various
    reasons.  Some of this has to do with fixing encodings before calling
    into the Django code.  Some of this has to do with providing a future
    path for instrumentation.  Some of it's just consistency.

    The linter will prevent direct calls to self.client.foo, so the wrapper
    functions have to fake out the linter by using a local variable called
    django_client to fool the regext.
    '''

    DEFAULT_REALM_NAME = 'zulip.com'

    @instrument_url
    def client_patch(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        """
        We need to urlencode, since Django's function won't do it for us.
        """
        encoded = urllib.parse.urlencode(info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.patch(url, encoded, **kwargs)

    @instrument_url
    def client_patch_multipart(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        """
        Use this for patch requests that have file uploads or
        that need some sort of multi-part content.  In the future
        Django's test client may become a bit more flexible,
        so we can hopefully eliminate this.  (When you post
        with the Django test client, it deals with MULTIPART_CONTENT
        automatically, but not patch.)
        """
        encoded = encode_multipart(BOUNDARY, info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.patch(
            url,
            encoded,
            content_type=MULTIPART_CONTENT,
            **kwargs)

    @instrument_url
    def client_put(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.put(url, encoded, **kwargs)

    @instrument_url
    def client_delete(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.delete(url, encoded, **kwargs)

    @instrument_url
    def client_post(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.post(url, info, **kwargs)

    @instrument_url
    def client_post_request(self, url, req):
        # type: (text_type, Any) -> HttpResponse
        """
        We simulate hitting an endpoint here, although we
        actually resolve the URL manually and hit the view
        directly.  We have this helper method to allow our
        instrumentation to work for /notify_tornado and
        future similar methods that require doing funny
        things to a request object.
        """

        match = resolve(url)
        return match.func(req)

    @instrument_url
    def client_get(self, url, info={}, **kwargs):
        # type: (text_type, Dict[str, Any], **Any) -> HttpResponse
        django_client = self.client # see WRAPPER_COMMENT
        return django_client.get(url, info, **kwargs)

    def login_with_return(self, email, password=None):
        # type: (text_type, Optional[text_type]) -> HttpResponse
        if password is None:
            password = initial_password(email)
        return self.client_post('/accounts/login/',
                                {'username': email, 'password': password})

    def login(self, email, password=None, fails=False):
        # type: (text_type, Optional[text_type], bool) -> HttpResponse
        if password is None:
            password = initial_password(email)
        if not fails:
            self.assertTrue(self.client.login(username=email, password=password))
        else:
            self.assertFalse(self.client.login(username=email, password=password))

    def register(self, username, password, domain="zulip.com"):
        # type: (text_type, text_type, text_type) -> HttpResponse
        self.client_post('/accounts/home/',
                         {'email': username + "@" + domain})
        return self.submit_reg_form_for_user(username, password, domain=domain)

    def submit_reg_form_for_user(self, username, password, domain="zulip.com",
                                 realm_name="Zulip Test", realm_subdomain="zuliptest",
                                 realm_org_type=Realm.COMMUNITY,
                                 from_confirmation='', **kwargs):
        # type: (text_type, text_type, text_type, Optional[text_type], Optional[text_type], int, Optional[text_type], **Any) -> HttpResponse
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.

        You can pass the HTTP_HOST variable for subdomains via kwargs.
        """
        return self.client_post('/accounts/register/',
                                {'full_name': username, 'password': password,
                                 'realm_name': realm_name,
                                 'realm_subdomain': realm_subdomain,
                                 'key': find_key_by_email(username + '@' + domain),
                                 'realm_org_type': realm_org_type,
                                 'terms': True,
                                 'from_confirmation': from_confirmation},
                                **kwargs)

    def get_confirmation_url_from_outbox(self, email_address, path_pattern="(\S+)>"):
        # type: (text_type, text_type) -> text_type
        from django.core.mail import outbox
        for message in reversed(outbox):
            if email_address in message.to:
                return re.search(settings.EXTERNAL_HOST + path_pattern,
                                 message.body).groups()[0]
        else:
            raise ValueError("Couldn't find a confirmation email.")

    def get_api_key(self, email):
        # type: (text_type) -> text_type
        if email not in API_KEYS:
            API_KEYS[email] = get_user_profile_by_email(email).api_key
        return API_KEYS[email]

    def api_auth(self, email):
        # type: (text_type) -> Dict[str, text_type]
        credentials = u"%s:%s" % (email, self.get_api_key(email))
        return {
            'HTTP_AUTHORIZATION': u'Basic ' + base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        }

    def get_streams(self, email):
        # type: (text_type) -> List[text_type]
        """
        Helper function to get the stream names for a user
        """
        user_profile = get_user_profile_by_email(email)
        subs = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            recipient__type=Recipient.STREAM)
        return [cast(text_type, get_display_recipient(sub.recipient)) for sub in subs]

    def send_message(self, sender_name, raw_recipients, message_type,
                     content=u"test content", subject=u"test", **kwargs):
        # type: (text_type, Union[text_type, List[text_type]], int, text_type, text_type, **Any) -> int
        sender = get_user_profile_by_email(sender_name)
        if message_type == Recipient.PERSONAL:
            message_type_name = "private"
        else:
            message_type_name = "stream"
        if isinstance(raw_recipients, six.string_types):
            recipient_list = [raw_recipients]
        else:
            recipient_list = raw_recipients
        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_message(
            sender, sending_client, message_type_name, recipient_list, subject,
            content, forged=False, forged_timestamp=None,
            forwarder_user_profile=sender, realm=sender.realm, **kwargs)

    def get_old_messages(self, anchor=1, num_before=100, num_after=100):
        # type: (int, int, int) -> List[Dict[str, Any]]
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after}
        result = self.client_get("/json/messages", dict(post_params))
        data = ujson.loads(result.content)
        return data['messages']

    def users_subscribed_to_stream(self, stream_name, realm_domain):
        # type: (text_type, text_type) -> List[UserProfile]
        realm = get_realm(realm_domain)
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient, active=True)

        return [subscription.user_profile for subscription in subscriptions]

    def assert_json_success(self, result):
        # type: (HttpResponse) -> Dict[str, Any]
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        self.assertEqual(result.status_code, 200, result)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertIn("msg", json)
        return json

    def get_json_error(self, result, status_code=400):
        # type: (HttpResponse, int) -> Dict[str, Any]
        self.assertEqual(result.status_code, status_code)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        return json['msg']

    def assert_json_error(self, result, msg, status_code=400):
        # type: (HttpResponse, text_type, int) -> None
        """
        Invalid POSTs return an error status code and JSON of the form
        {"result": "error", "msg": "reason"}.
        """
        self.assertEqual(self.get_json_error(result, status_code=status_code), msg)

    def assert_length(self, queries, count):
        # type: (Sized, int) -> None
        actual_count = len(queries)
        return self.assertTrue(actual_count == count,
                                   "len(%s) == %s, != %s" % (queries, actual_count, count))

    def assert_max_length(self, queries, count):
        # type: (Sized, int) -> None
        actual_count = len(queries)
        return self.assertTrue(actual_count <= count,
                               "len(%s) == %s, > %s" % (queries, actual_count, count))

    def assert_json_error_contains(self, result, msg_substring, status_code=400):
        # type: (HttpResponse, text_type, int) -> None
        self.assertIn(msg_substring, self.get_json_error(result, status_code=status_code))

    def assert_equals_response(self, string, response):
        # type: (text_type, HttpResponse) -> None
        self.assertEqual(string, response.content.decode('utf-8'))

    def assert_in_response(self, substring, response):
        # type: (text_type, HttpResponse) -> None
        self.assertIn(substring, response.content.decode('utf-8'))

    def fixture_data(self, type, action, file_type='json'):
        # type: (text_type, text_type, text_type) -> text_type
        return force_text(open(os.path.join(os.path.dirname(__file__),
                                            "../fixtures/%s/%s_%s.%s" % (type, type, action, file_type))).read())

    def make_stream(self, stream_name, realm=None, invite_only=False):
        # type: (text_type, Optional[Realm], Optional[bool]) -> Stream
        if realm is None:
            realm = get_realm(self.DEFAULT_REALM_NAME)

        try:
            stream = Stream.objects.create(
                realm=realm,
                name=stream_name,
                invite_only=invite_only,
            )
        except IntegrityError:
            raise Exception('''
                %s already exists

                Please call make_stream with a stream name
                that is not already in use.''' % (stream_name,))

        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        return stream

    # Subscribe to a stream directly
    def subscribe_to_stream(self, email, stream_name, realm=None):
        # type: (text_type, text_type, Optional[Realm]) -> None
        if realm is None:
            realm = get_realm_by_email_domain(email)
        stream = get_stream(stream_name, realm)
        if stream is None:
            stream, _ = create_stream_if_needed(realm, stream_name)
        user_profile = get_user_profile_by_email(email)
        bulk_add_subscriptions([stream], [user_profile])

    def unsubscribe_from_stream(self, email, stream_name):
        # type: (text_type, text_type) -> None
        user_profile = get_user_profile_by_email(email)
        stream = get_stream(stream_name, user_profile.realm)
        bulk_remove_subscriptions([user_profile], [stream])

    # Subscribe to a stream by making an API request
    def common_subscribe_to_streams(self, email, streams, extra_post_data={}, invite_only=False):
        # type: (text_type, Iterable[text_type], Dict[str, Any], bool) -> HttpResponse
        post_data = {'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)
        result = self.client_post("/api/v1/users/me/subscriptions", post_data, **self.api_auth(email))
        return result

    def send_json_payload(self, email, url, payload, stream_name=None, **post_params):
        # type: (text_type, text_type, Union[text_type, Dict[str, Any]], Optional[text_type], **Any) -> Message
        if stream_name is not None:
            self.subscribe_to_stream(email, stream_name)

        result = self.client_post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()
        self.assertEqual(msg.sender.email, email)
        if stream_name is not None:
            self.assertEqual(get_display_recipient(msg.recipient), stream_name)
        # TODO: should also validate recipient for private messages

        return msg

    def get_last_message(self):
        # type: () -> Message
        return Message.objects.latest('id')

    def get_second_to_last_message(self):
        # type: () -> Message
        return Message.objects.all().order_by('-id')[1]

    @contextmanager
    def simulated_markdown_failure(self):
        # type: () -> Generator[None, None, None]
        '''
        This raises a failure inside of the try/except block of
        bugdown.__init__.do_convert.
        '''
        with \
                self.settings(ERROR_BOT=None), \
                mock.patch('zerver.lib.bugdown.timeout', side_effect=KeyError('foo')), \
                mock.patch('zerver.lib.bugdown.log_bugdown_error'):
            yield

class WebhookTestCase(ZulipTestCase):
    """
    Common for all webhooks tests

    Override below class attributes and run send_and_test_message
    If you create your url in uncommon way you can override build_webhook_url method
    In case that you need modify body or create it without using fixture you can also override get_body method
    """
    STREAM_NAME = None # type: Optional[text_type]
    TEST_USER_EMAIL = 'webhook-bot@zulip.com'
    URL_TEMPLATE = None # type: Optional[text_type]
    FIXTURE_DIR_NAME = None # type: Optional[text_type]

    def setUp(self):
        # type: () -> None
        self.url = self.build_webhook_url()

    def send_and_test_stream_message(self, fixture_name, expected_subject=None,
                                     expected_message=None, content_type="application/json", **kwargs):
        # type: (text_type, Optional[text_type], Optional[text_type], Optional[text_type], **Any) -> Message
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type
        msg = self.send_json_payload(self.TEST_USER_EMAIL, self.url, payload,
                                     self.STREAM_NAME, **kwargs)
        self.do_test_subject(msg, expected_subject)
        self.do_test_message(msg, expected_message)

        return msg

    def send_and_test_private_message(self, fixture_name, expected_subject=None,
                                      expected_message=None, content_type="application/json", **kwargs):
        # type: (text_type, text_type, text_type, str, **Any) -> Message
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type

        msg = self.send_json_payload(self.TEST_USER_EMAIL, self.url, payload,
                                     stream_name=None, **kwargs)
        self.do_test_message(msg, expected_message)

        return msg

    def build_webhook_url(self):
        # type: () -> text_type
        api_key = self.get_api_key(self.TEST_USER_EMAIL)
        return self.URL_TEMPLATE.format(stream=self.STREAM_NAME, api_key=api_key)

    def get_body(self, fixture_name):
        # type: (text_type) -> Union[text_type, Dict[str, text_type]]
        """Can be implemented either as returning a dictionary containing the
        post parameters or as string containing the body of the request."""
        return ujson.dumps(ujson.loads(self.fixture_data(self.FIXTURE_DIR_NAME, fixture_name)))

    def do_test_subject(self, msg, expected_subject):
        # type: (Message, Optional[text_type]) -> None
        if expected_subject is not None:
            self.assertEqual(msg.topic_name(), expected_subject)

    def do_test_message(self, msg, expected_message):
        # type: (Message, Optional[text_type]) -> None
        if expected_message is not None:
            self.assertEqual(msg.content, expected_message)
