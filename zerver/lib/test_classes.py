from __future__ import absolute_import
from __future__ import print_function
from contextlib import contextmanager
from typing import (cast, Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional,
                    Sized, Tuple, Union, Text)

from django.core.urlresolvers import resolve
from django.conf import settings
from django.test import TestCase
from django.test.client import (
    BOUNDARY, MULTIPART_CONTENT, encode_multipart,
)
from django.template import loader
from django.test.testcases import SerializeMixin
from django.http import HttpResponse
from django.db.utils import IntegrityError

from zerver.lib.initial_password import initial_password
from zerver.lib.db import TimeTrackingCursor
from zerver.lib.str_utils import force_text
from zerver.lib.utils import is_remote_server
from zerver.lib import cache
from zerver.tornado.handlers import allocate_handler_id
from zerver.worker import queue_processors

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, bulk_add_subscriptions,
    get_display_recipient, bulk_remove_subscriptions
)

from zerver.lib.test_helpers import (
    instrument_url, find_key_by_email,
)

from zerver.models import (
    get_stream,
    get_user,
    get_user_profile_by_email,
    get_realm,
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
from zilencer.models import get_remote_server_by_uuid


import base64
import mock
import os
import re
import time
import ujson
import unittest
from six.moves import urllib
from six import binary_type
from zerver.lib.str_utils import NonBinaryStr

from contextlib import contextmanager
import six

API_KEYS = {}  # type: Dict[Text, Text]

def flush_caches_for_testing():
    # type: () -> None
    global API_KEYS
    API_KEYS = {}

class UploadSerializeMixin(SerializeMixin):
    """
    We cannot use override_settings to change upload directory because
    because settings.LOCAL_UPLOADS_DIR is used in url pattern and urls
    are compiled only once. Otherwise using a different upload directory
    for conflicting test cases would have provided better performance
    while providing the required isolation.
    """
    lockfile = 'var/upload_lock'

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        # type: (*Any, **Any) -> None
        if not os.path.exists(cls.lockfile):
            with open(cls.lockfile, 'w'):  # nocoverage - rare locking case
                pass

        super(UploadSerializeMixin, cls).setUpClass(*args, **kwargs)

class ZulipTestCase(TestCase):
    # Ensure that the test system just shows us diffs
    maxDiff = None  # type: Optional[int]

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
    DEFAULT_SUBDOMAIN = "zulip"
    DEFAULT_REALM = Realm.objects.get(string_id='zulip')

    def set_http_host(self, kwargs):
        # type: (Dict[str, Any]) -> None
        if 'subdomain' in kwargs:
            if kwargs['subdomain'] != "":
                kwargs["HTTP_HOST"] = "%s.%s" % (kwargs["subdomain"], settings.EXTERNAL_HOST)
            else:
                kwargs["HTTP_HOST"] = settings.EXTERNAL_HOST
            del kwargs['subdomain']
        elif 'HTTP_HOST' not in kwargs:
            if self.DEFAULT_SUBDOMAIN == "":
                kwargs["HTTP_HOST"] = settings.EXTERNAL_HOST
            else:
                kwargs["HTTP_HOST"] = "%s.%s" % (self.DEFAULT_SUBDOMAIN,
                                                 settings.EXTERNAL_HOST,)

    @instrument_url
    def client_patch(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        """
        We need to urlencode, since Django's function won't do it for us.
        """
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.patch(url, encoded, **kwargs)

    @instrument_url
    def client_patch_multipart(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        """
        Use this for patch requests that have file uploads or
        that need some sort of multi-part content.  In the future
        Django's test client may become a bit more flexible,
        so we can hopefully eliminate this.  (When you post
        with the Django test client, it deals with MULTIPART_CONTENT
        automatically, but not patch.)
        """
        encoded = encode_multipart(BOUNDARY, info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.patch(
            url,
            encoded,
            content_type=MULTIPART_CONTENT,
            **kwargs)

    @instrument_url
    def client_put(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.put(url, encoded, **kwargs)

    @instrument_url
    def client_delete(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.delete(url, encoded, **kwargs)

    @instrument_url
    def client_options(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.options(url, encoded, **kwargs)

    @instrument_url
    def client_head(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.head(url, encoded, **kwargs)

    @instrument_url
    def client_post(self, url, info={}, **kwargs):
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.post(url, info, **kwargs)

    @instrument_url
    def client_post_request(self, url, req):
        # type: (Text, Any) -> HttpResponse
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
        # type: (Text, Dict[str, Any], **Any) -> HttpResponse
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.get(url, info, **kwargs)

    example_user_map = dict(
        hamlet=u'hamlet@zulip.com',
        cordelia=u'cordelia@zulip.com',
        iago=u'iago@zulip.com',
        prospero=u'prospero@zulip.com',
        othello=u'othello@zulip.com',
        AARON=u'AARON@zulip.com',
        aaron=u'aaron@zulip.com',
        ZOE=u'ZOE@zulip.com',
        webhook_bot=u'webhook-bot@zulip.com',
    )

    mit_user_map = dict(
        sipbtest=u"sipbtest@mit.edu",
        starnine=u"starnine@mit.edu",
        espuser=u"espuser@mit.edu",
    )

    # Non-registered test users
    nonreg_user_map = dict(
        test=u'test@zulip.com',
        test1=u'test1@zulip.com',
        alice=u'alice@zulip.com',
        newuser=u'newuser@zulip.com',
        bob=u'bob@zulip.com',
        cordelia=u'cordelia@zulip.com',
        newguy=u'newguy@zulip.com',
        me=u'me@zulip.com',
    )

    def nonreg_user(self, name):
        # type: (str) -> UserProfile
        email = self.nonreg_user_map[name]
        return get_user(email, get_realm("zulip"))

    def example_user(self, name):
        # type: (str) -> UserProfile
        email = self.example_user_map[name]
        return get_user(email, get_realm('zulip'))

    def mit_user(self, name):
        # type: (str) -> UserProfile
        email = self.mit_user_map[name]
        return get_user(email, get_realm('zephyr'))

    def nonreg_email(self, name):
        # type: (str) -> Text
        return self.nonreg_user_map[name]

    def example_email(self, name):
        # type: (str) -> Text
        return self.example_user_map[name]

    def mit_email(self, name):
        # type: (str) -> Text
        return self.mit_user_map[name]

    def notification_bot(self):
        # type: () -> UserProfile
        return get_user('notification-bot@zulip.com', get_realm('zulip'))

    def login_with_return(self, email, password=None, **kwargs):
        # type: (Text, Optional[Text], **Any) -> HttpResponse
        if password is None:
            password = initial_password(email)
        return self.client_post('/accounts/login/',
                                {'username': email, 'password': password},
                                **kwargs)

    def login(self, email, password=None, fails=False):
        # type: (Text, Optional[Text], bool) -> HttpResponse
        if password is None:
            password = initial_password(email)
        if not fails:
            self.assertTrue(self.client.login(username=email, password=password))
        else:
            self.assertFalse(self.client.login(username=email, password=password))

    def logout(self):
        # type: () -> None
        self.client.logout()

    def register(self, email, password, **kwargs):
        # type: (Text, Text, **Any) -> HttpResponse
        self.client_post('/accounts/home/', {'email': email},
                         **kwargs)
        return self.submit_reg_form_for_user(email, password, **kwargs)

    def submit_reg_form_for_user(self, email, password, realm_name="Zulip Test",
                                 realm_subdomain="zuliptest",
                                 from_confirmation='', full_name=None, timezone=u'', **kwargs):
        # type: (Text, Text, Optional[Text], Optional[Text], Optional[Text], Optional[Text], Optional[Text], **Any) -> HttpResponse
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.

        You can pass the HTTP_HOST variable for subdomains via kwargs.
        """
        if full_name is None:
            full_name = email.replace("@", "_")
        return self.client_post('/accounts/register/',
                                {'full_name': full_name,
                                 'password': password,
                                 'realm_name': realm_name,
                                 'realm_subdomain': realm_subdomain,
                                 'key': find_key_by_email(email),
                                 'timezone': timezone,
                                 'terms': True,
                                 'from_confirmation': from_confirmation},
                                **kwargs)

    def get_confirmation_url_from_outbox(self, email_address, path_pattern="(\S+)>"):
        # type: (Text, Text) -> Text
        from django.core.mail import outbox
        for message in reversed(outbox):
            if email_address in message.to:
                return re.search(settings.EXTERNAL_HOST + path_pattern,
                                 message.body).groups()[0]
        else:
            raise AssertionError("Couldn't find a confirmation email.")

    def api_auth(self, identifier):
        # type: (Text) -> Dict[str, Text]
        """
        identifier: Can be an email or a remote server uuid.
        """
        if identifier in API_KEYS:
            api_key = API_KEYS[identifier]
        else:
            if is_remote_server(identifier):
                api_key = get_remote_server_by_uuid(identifier).api_key
            else:
                api_key = get_user_profile_by_email(identifier).api_key
            API_KEYS[identifier] = api_key

        credentials = u"%s:%s" % (identifier, api_key)
        return {
            'HTTP_AUTHORIZATION': u'Basic ' + base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        }

    def get_streams(self, email, realm):
        # type: (Text, Realm) -> List[Text]
        """
        Helper function to get the stream names for a user
        """
        user_profile = get_user(email, realm)
        subs = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            recipient__type=Recipient.STREAM)
        return [cast(Text, get_display_recipient(sub.recipient)) for sub in subs]

    def send_message(self, sender_name, raw_recipients, message_type,
                     content=u"test content", subject=u"test", **kwargs):
        # type: (Text, Union[Text, List[Text]], int, Text, Text, **Any) -> int
        sender = get_user_profile_by_email(sender_name)
        if message_type in [Recipient.PERSONAL, Recipient.HUDDLE]:
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

    def get_messages(self, anchor=1, num_before=100, num_after=100,
                     use_first_unread_anchor=False):
        # type: (int, int, int, bool) -> List[Dict[str, Any]]
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after,
                       "use_first_unread_anchor": ujson.dumps(use_first_unread_anchor)}
        result = self.client_get("/json/messages", dict(post_params))
        data = result.json()
        return data['messages']

    def users_subscribed_to_stream(self, stream_name, realm):
        # type: (Text, Realm) -> List[UserProfile]
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient, active=True)

        return [subscription.user_profile for subscription in subscriptions]

    def assert_url_serves_contents_of_file(self, url, result):
        # type: (str, bytes) -> None
        response = self.client_get(url)
        data = b"".join(response.streaming_content)
        self.assertEqual(result, data)

    def assert_json_success(self, result):
        # type: (HttpResponse) -> Dict[str, Any]
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        try:
            json = ujson.loads(result.content)
        except Exception:  # nocoverage
            json = {'msg': "Error parsing JSON in response!"}
        self.assertEqual(result.status_code, 200, json['msg'])
        self.assertEqual(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertIn("msg", json)
        self.assertNotEqual(json["msg"], "Error parsing JSON in response!")
        return json

    def get_json_error(self, result, status_code=400):
        # type: (HttpResponse, int) -> Dict[str, Any]
        try:
            json = ujson.loads(result.content)
        except Exception:  # nocoverage
            json = {'msg': "Error parsing JSON in response!"}
        self.assertEqual(result.status_code, status_code, msg=json.get('msg'))
        self.assertEqual(json.get("result"), "error")
        return json['msg']

    def assert_json_error(self, result, msg, status_code=400):
        # type: (HttpResponse, Text, int) -> None
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

    def assert_json_error_contains(self, result, msg_substring, status_code=400):
        # type: (HttpResponse, Text, int) -> None
        self.assertIn(msg_substring, self.get_json_error(result, status_code=status_code))

    def assert_in_response(self, substring, response):
        # type: (Text, HttpResponse) -> None
        self.assertIn(substring, response.content.decode('utf-8'))

    def assert_in_success_response(self, substrings, response):
        # type: (List[Text], HttpResponse) -> None
        self.assertEqual(response.status_code, 200)
        decoded = response.content.decode('utf-8')
        for substring in substrings:
            self.assertIn(substring, decoded)

    def assert_not_in_success_response(self, substrings, response):
        # type: (List[Text], HttpResponse) -> None
        self.assertEqual(response.status_code, 200)
        decoded = response.content.decode('utf-8')
        for substring in substrings:
            self.assertNotIn(substring, decoded)

    def fixture_data(self, type, action, file_type='json'):
        # type: (Text, Text, Text) -> Text
        return force_text(open(os.path.join(os.path.dirname(__file__),
                                            "../webhooks/%s/fixtures/%s.%s" % (type, action, file_type))).read())

    def make_stream(self, stream_name, realm=None, invite_only=False):
        # type: (Text, Optional[Realm], Optional[bool]) -> Stream
        if realm is None:
            realm = self.DEFAULT_REALM

        try:
            stream = Stream.objects.create(
                realm=realm,
                name=stream_name,
                invite_only=invite_only,
            )
        except IntegrityError:  # nocoverage -- this is for bugs in the tests
            raise Exception('''
                %s already exists

                Please call make_stream with a stream name
                that is not already in use.''' % (stream_name,))

        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        return stream

    # Subscribe to a stream directly
    def subscribe(self, user_profile, stream_name):
        # type: (UserProfile, Text) -> Stream
        try:
            stream = get_stream(stream_name, user_profile.realm)
            from_stream_creation = False
        except Stream.DoesNotExist:
            stream, from_stream_creation = create_stream_if_needed(user_profile.realm, stream_name)
        bulk_add_subscriptions([stream], [user_profile], from_stream_creation=from_stream_creation)
        return stream

    def unsubscribe(self, user_profile, stream_name):
        # type: (UserProfile, Text) -> None
        stream = get_stream(stream_name, user_profile.realm)
        bulk_remove_subscriptions([user_profile], [stream])

    # Subscribe to a stream by making an API request
    def common_subscribe_to_streams(self, email, streams, extra_post_data={}, invite_only=False,
                                    **kwargs):
        # type: (Text, Iterable[Text], Dict[str, Any], bool, **Any) -> HttpResponse
        post_data = {'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)
        kw = kwargs.copy()
        kw.update(self.api_auth(email))
        result = self.client_post("/api/v1/users/me/subscriptions", post_data,
                                  **kw)
        return result

    def send_json_payload(self, user_profile, url, payload, stream_name=None, **post_params):
        # type: (UserProfile, Text, Union[Text, Dict[str, Any]], Optional[Text], **Any) -> Message
        if stream_name is not None:
            self.subscribe(user_profile, stream_name)

        result = self.client_post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()
        self.assertEqual(msg.sender.email, user_profile.email)
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
        # type: () -> Iterator[None]
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
    STREAM_NAME = None  # type: Optional[Text]
    TEST_USER_EMAIL = 'webhook-bot@zulip.com'
    URL_TEMPLATE = None  # type: Optional[Text]
    FIXTURE_DIR_NAME = None  # type: Optional[Text]

    @property
    def test_user(self):
        # type: () -> UserProfile
        return get_user(self.TEST_USER_EMAIL, get_realm("zulip"))

    def setUp(self):
        # type: () -> None
        self.url = self.build_webhook_url()

    def send_and_test_stream_message(self, fixture_name, expected_subject=None,
                                     expected_message=None, content_type="application/json", **kwargs):
        # type: (Text, Optional[Text], Optional[Text], Optional[Text], **Any) -> Message
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type
        msg = self.send_json_payload(self.test_user, self.url, payload,
                                     self.STREAM_NAME, **kwargs)
        self.do_test_subject(msg, expected_subject)
        self.do_test_message(msg, expected_message)

        return msg

    def send_and_test_private_message(self, fixture_name, expected_subject=None,
                                      expected_message=None, content_type="application/json", **kwargs):
        # type: (Text, Text, Text, str, **Any) -> Message
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type

        msg = self.send_json_payload(self.test_user, self.url, payload,
                                     stream_name=None, **kwargs)
        self.do_test_message(msg, expected_message)

        return msg

    def build_webhook_url(self, *args, **kwargs):
        # type: (*Any, **Any) -> Text
        url = self.URL_TEMPLATE
        if url.find("api_key") >= 0:
            api_key = self.test_user.api_key
            url = self.URL_TEMPLATE.format(api_key=api_key,
                                           stream=self.STREAM_NAME)
        else:
            url = self.URL_TEMPLATE.format(stream=self.STREAM_NAME)

        has_arguments = kwargs or args
        if has_arguments and url.find('?') == -1:
            url = "{}?".format(url)
        else:
            url = "{}&".format(url)

        for key, value in kwargs.items():
            url = "{}{}={}&".format(url, key, value)

        for arg in args:
            url = "{}{}&".format(url, arg)

        return url[:-1] if has_arguments else url

    def get_body(self, fixture_name):
        # type: (Text) -> Union[Text, Dict[str, Text]]
        """Can be implemented either as returning a dictionary containing the
        post parameters or as string containing the body of the request."""
        return ujson.dumps(ujson.loads(self.fixture_data(self.FIXTURE_DIR_NAME, fixture_name)))

    def do_test_subject(self, msg, expected_subject):
        # type: (Message, Optional[Text]) -> None
        if expected_subject is not None:
            self.assertEqual(msg.topic_name(), expected_subject)

    def do_test_message(self, msg, expected_message):
        # type: (Message, Optional[Text]) -> None
        if expected_message is not None:
            self.assertEqual(msg.content, expected_message)
