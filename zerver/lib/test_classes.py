from contextlib import contextmanager
from typing import (cast, Any, Dict, Iterable, Iterator, List, Optional,
                    Tuple, Union)

from django.apps import apps
from django.db.migrations.state import StateApps
from django.urls import resolve
from django.conf import settings
from django.test import TestCase
from django.test.client import (
    BOUNDARY, MULTIPART_CONTENT, encode_multipart,
)
from django.test.testcases import SerializeMixin
from django.http import HttpResponse
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from django.db.utils import IntegrityError
from django.http import HttpRequest

from two_factor.models import PhoneDevice
from zerver.lib.initial_password import initial_password
from zerver.lib.utils import is_remote_server
from zerver.lib.users import get_api_key

from zerver.lib.actions import (
    check_send_message, create_stream_if_needed, bulk_add_subscriptions,
    bulk_remove_subscriptions,
    check_send_stream_message, gather_subscriptions,
    get_default_value_for_history_public_to_subscribers,
)

from zerver.lib.stream_subscription import (
    get_stream_subscriptions_for_user,
)

from zerver.lib.test_helpers import (
    instrument_url, find_key_by_email,
)

from zerver.models import (
    get_stream,
    get_client,
    get_display_recipient,
    get_user,
    get_realm,
    Client,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
)
from zilencer.models import get_remote_server_by_uuid
from zerver.decorator import do_two_factor_login
from zerver.tornado.event_queue import clear_client_event_queues_for_testing

import base64
import mock
import os
import re
import ujson
import urllib

API_KEYS = {}  # type: Dict[str, str]

def flush_caches_for_testing() -> None:
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
    def setUpClass(cls: Any, *args: Any, **kwargs: Any) -> None:
        if not os.path.exists(cls.lockfile):
            with open(cls.lockfile, 'w'):  # nocoverage - rare locking case
                pass

        super(UploadSerializeMixin, cls).setUpClass(*args, **kwargs)

class ZulipTestCase(TestCase):
    # Ensure that the test system just shows us diffs
    maxDiff = None  # type: Optional[int]

    def tearDown(self) -> None:
        super().tearDown()
        # Important: we need to clear event queues to avoid leaking data to future tests.
        clear_client_event_queues_for_testing()

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
    TOKENIZED_NOREPLY_REGEX = settings.TOKENIZED_NOREPLY_EMAIL_ADDRESS.format(token="[a-z0-9_]{24}")

    def set_http_host(self, kwargs: Dict[str, Any]) -> None:
        if 'subdomain' in kwargs:
            kwargs['HTTP_HOST'] = Realm.host_for_subdomain(kwargs['subdomain'])
            del kwargs['subdomain']
        elif 'HTTP_HOST' not in kwargs:
            kwargs['HTTP_HOST'] = Realm.host_for_subdomain(self.DEFAULT_SUBDOMAIN)

    @instrument_url
    def client_patch(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        """
        We need to urlencode, since Django's function won't do it for us.
        """
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.patch(url, encoded, **kwargs)

    @instrument_url
    def client_patch_multipart(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
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
    def client_put(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.put(url, encoded, **kwargs)

    @instrument_url
    def client_delete(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.delete(url, encoded, **kwargs)

    @instrument_url
    def client_options(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.options(url, encoded, **kwargs)

    @instrument_url
    def client_head(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        encoded = urllib.parse.urlencode(info)
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.head(url, encoded, **kwargs)

    @instrument_url
    def client_post(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.post(url, info, **kwargs)

    @instrument_url
    def client_post_request(self, url: str, req: Any) -> HttpResponse:
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
    def client_get(self, url: str, info: Dict[str, Any]={}, **kwargs: Any) -> HttpResponse:
        django_client = self.client  # see WRAPPER_COMMENT
        self.set_http_host(kwargs)
        return django_client.get(url, info, **kwargs)

    example_user_map = dict(
        hamlet='hamlet@zulip.com',
        cordelia='cordelia@zulip.com',
        iago='iago@zulip.com',
        prospero='prospero@zulip.com',
        othello='othello@zulip.com',
        AARON='AARON@zulip.com',
        aaron='aaron@zulip.com',
        ZOE='ZOE@zulip.com',
        polonius='polonius@zulip.com',
        webhook_bot='webhook-bot@zulip.com',
        welcome_bot='welcome-bot@zulip.com',
        outgoing_webhook_bot='outgoing-webhook@zulip.com'
    )

    mit_user_map = dict(
        sipbtest="sipbtest@mit.edu",
        starnine="starnine@mit.edu",
        espuser="espuser@mit.edu",
    )

    lear_user_map = dict(
        cordelia="cordelia@zulip.com",
        king="king@lear.org"
    )

    # Non-registered test users
    nonreg_user_map = dict(
        test='test@zulip.com',
        test1='test1@zulip.com',
        alice='alice@zulip.com',
        newuser='newuser@zulip.com',
        bob='bob@zulip.com',
        cordelia='cordelia@zulip.com',
        newguy='newguy@zulip.com',
        me='me@zulip.com',
    )

    def nonreg_user(self, name: str) -> UserProfile:
        email = self.nonreg_user_map[name]
        return get_user(email, get_realm("zulip"))

    def example_user(self, name: str) -> UserProfile:
        email = self.example_user_map[name]
        return get_user(email, get_realm('zulip'))

    def mit_user(self, name: str) -> UserProfile:
        email = self.mit_user_map[name]
        return get_user(email, get_realm('zephyr'))

    def lear_user(self, name: str) -> UserProfile:
        email = self.lear_user_map[name]
        return get_user(email, get_realm('lear'))

    def nonreg_email(self, name: str) -> str:
        return self.nonreg_user_map[name]

    def example_email(self, name: str) -> str:
        return self.example_user_map[name]

    def mit_email(self, name: str) -> str:
        return self.mit_user_map[name]

    def notification_bot(self) -> UserProfile:
        return get_user('notification-bot@zulip.com', get_realm('zulip'))

    def create_test_bot(self, short_name: str, user_profile: UserProfile,
                        assert_json_error_msg: str=None, **extras: Any) -> Optional[UserProfile]:
        self.login(user_profile.email)
        bot_info = {
            'short_name': short_name,
            'full_name': 'Foo Bot',
        }
        bot_info.update(extras)
        result = self.client_post("/json/bots", bot_info)
        if assert_json_error_msg is not None:
            self.assert_json_error(result, assert_json_error_msg)
            return None
        else:
            self.assert_json_success(result)
            bot_email = '{}-bot@zulip.testserver'.format(short_name)
            bot_profile = get_user(bot_email, user_profile.realm)
            return bot_profile

    def login_with_return(self, email: str, password: Optional[str]=None,
                          **kwargs: Any) -> HttpResponse:
        if password is None:
            password = initial_password(email)
        result = self.client_post('/accounts/login/',
                                  {'username': email, 'password': password},
                                  **kwargs)
        self.assertNotEqual(result.status_code, 500)
        return result

    def login(self, email: str, password: Optional[str]=None, fails: bool=False,
              realm: Optional[Realm]=None) -> HttpResponse:
        if realm is None:
            realm = get_realm("zulip")
        if password is None:
            password = initial_password(email)
        if not fails:
            self.assertTrue(self.client.login(username=email, password=password,
                                              realm=realm))
        else:
            self.assertFalse(self.client.login(username=email, password=password,
                                               realm=realm))

    def login_2fa(self, user_profile: UserProfile) -> None:
        """
        We need this function to call request.session.save().
        do_two_factor_login doesn't save session; in normal request-response
        cycle this doesn't matter because middleware will save the session
        when it finds it dirty; however,in tests we will have to do that
        explicitly.
        """
        request = HttpRequest()
        request.session = self.client.session
        request.user = user_profile
        do_two_factor_login(request, user_profile)
        request.session.save()

    def logout(self) -> None:
        self.client.logout()

    def register(self, email: str, password: str, **kwargs: Any) -> HttpResponse:
        self.client_post('/accounts/home/', {'email': email},
                         **kwargs)
        return self.submit_reg_form_for_user(email, password, **kwargs)

    def submit_reg_form_for_user(
            self, email: str, password: str,
            realm_name: Optional[str]="Zulip Test",
            realm_subdomain: Optional[str]="zuliptest",
            from_confirmation: Optional[str]='', full_name: Optional[str]=None,
            timezone: Optional[str]='', realm_in_root_domain: Optional[str]=None,
            default_stream_groups: Optional[List[str]]=[],
            source_realm: Optional[str]='', **kwargs: Any) -> HttpResponse:
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.

        You can pass the HTTP_HOST variable for subdomains via kwargs.
        """
        if full_name is None:
            full_name = email.replace("@", "_")
        payload = {
            'full_name': full_name,
            'password': password,
            'realm_name': realm_name,
            'realm_subdomain': realm_subdomain,
            'key': find_key_by_email(email),
            'timezone': timezone,
            'terms': True,
            'from_confirmation': from_confirmation,
            'default_stream_group': default_stream_groups,
            'source_realm': source_realm,
        }
        if realm_in_root_domain is not None:
            payload['realm_in_root_domain'] = realm_in_root_domain
        return self.client_post('/accounts/register/', payload, **kwargs)

    def get_confirmation_url_from_outbox(self, email_address: str, *,
                                         url_pattern: str=None) -> str:
        from django.core.mail import outbox
        if url_pattern is None:
            # This is a bit of a crude heuristic, but good enough for most tests.
            url_pattern = settings.EXTERNAL_HOST + r"(\S+)>"
        for message in reversed(outbox):
            if email_address in message.to:
                return re.search(url_pattern, message.body).groups()[0]
        else:
            raise AssertionError("Couldn't find a confirmation email.")

    def encode_credentials(self, identifier: str, realm: str="zulip") -> str:
        """
        identifier: Can be an email or a remote server uuid.
        """
        if identifier in API_KEYS:
            api_key = API_KEYS[identifier]
        else:
            if is_remote_server(identifier):
                api_key = get_remote_server_by_uuid(identifier).api_key
            else:
                user = get_user(identifier, get_realm(realm))
                api_key = get_api_key(user)
            API_KEYS[identifier] = api_key

        credentials = "%s:%s" % (identifier, api_key)
        return 'Basic ' + base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    def api_get(self, email: str, *args: Any, **kwargs: Any) -> HttpResponse:
        kwargs['HTTP_AUTHORIZATION'] = self.encode_credentials(email)
        return self.client_get(*args, **kwargs)

    def api_post(self, identifier: str, *args: Any, **kwargs: Any) -> HttpResponse:
        kwargs['HTTP_AUTHORIZATION'] = self.encode_credentials(identifier, kwargs.get('realm', 'zulip'))
        return self.client_post(*args, **kwargs)

    def api_patch(self, email: str, *args: Any, **kwargs: Any) -> HttpResponse:
        kwargs['HTTP_AUTHORIZATION'] = self.encode_credentials(email)
        return self.client_patch(*args, **kwargs)

    def api_put(self, email: str, *args: Any, **kwargs: Any) -> HttpResponse:
        kwargs['HTTP_AUTHORIZATION'] = self.encode_credentials(email)
        return self.client_put(*args, **kwargs)

    def api_delete(self, email: str, *args: Any, **kwargs: Any) -> HttpResponse:
        kwargs['HTTP_AUTHORIZATION'] = self.encode_credentials(email)
        return self.client_delete(*args, **kwargs)

    def get_streams(self, email: str, realm: Realm) -> List[str]:
        """
        Helper function to get the stream names for a user
        """
        user_profile = get_user(email, realm)
        subs = get_stream_subscriptions_for_user(user_profile).filter(
            active=True,
        )
        return [cast(str, get_display_recipient(sub.recipient)) for sub in subs]

    def send_personal_message(self, from_email: str, to_email: str, content: str="test content",
                              sender_realm: str="zulip") -> int:
        sender = get_user(from_email, get_realm(sender_realm))

        recipient_list = [to_email]
        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_message(
            sender, sending_client, 'private', recipient_list, None,
            content
        )

    def send_huddle_message(self, from_email: str, to_emails: List[str], content: str="test content",
                            sender_realm: str="zulip") -> int:
        sender = get_user(from_email, get_realm(sender_realm))

        assert(len(to_emails) >= 2)

        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_message(
            sender, sending_client, 'private', to_emails, None,
            content
        )

    def send_stream_message(self, sender_email: str, stream_name: str, content: str="test content",
                            topic_name: str="test", sender_realm: str="zulip") -> int:
        sender = get_user(sender_email, get_realm(sender_realm))

        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_stream_message(
            sender=sender,
            client=sending_client,
            stream_name=stream_name,
            topic=topic_name,
            body=content,
        )

    def get_messages_response(self, anchor: int=1, num_before: int=100, num_after: int=100,
                              use_first_unread_anchor: bool=False) -> Dict[str, List[Dict[str, Any]]]:
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after,
                       "use_first_unread_anchor": ujson.dumps(use_first_unread_anchor)}
        result = self.client_get("/json/messages", dict(post_params))
        data = result.json()
        return data

    def get_messages(self, anchor: int=1, num_before: int=100, num_after: int=100,
                     use_first_unread_anchor: bool=False) -> List[Dict[str, Any]]:
        data = self.get_messages_response(anchor, num_before, num_after, use_first_unread_anchor)
        return data['messages']

    def users_subscribed_to_stream(self, stream_name: str, realm: Realm) -> List[UserProfile]:
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient, active=True)

        return [subscription.user_profile for subscription in subscriptions]

    def assert_url_serves_contents_of_file(self, url: str, result: bytes) -> None:
        response = self.client_get(url)
        data = b"".join(response.streaming_content)
        self.assertEqual(result, data)

    def assert_json_success(self, result: HttpResponse) -> Dict[str, Any]:
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

    def get_json_error(self, result: HttpResponse, status_code: int=400) -> Dict[str, Any]:
        try:
            json = ujson.loads(result.content)
        except Exception:  # nocoverage
            json = {'msg': "Error parsing JSON in response!"}
        self.assertEqual(result.status_code, status_code, msg=json.get('msg'))
        self.assertEqual(json.get("result"), "error")
        return json['msg']

    def assert_json_error(self, result: HttpResponse, msg: str, status_code: int=400) -> None:
        """
        Invalid POSTs return an error status code and JSON of the form
        {"result": "error", "msg": "reason"}.
        """
        self.assertEqual(self.get_json_error(result, status_code=status_code), msg)

    def assert_length(self, items: List[Any], count: int) -> None:
        actual_count = len(items)
        if actual_count != count:  # nocoverage
            print('ITEMS:\n')
            for item in items:
                print(item)
            print("\nexpected length: %s\nactual length: %s" % (count, actual_count))
            raise AssertionError('List is unexpected size!')

    def assert_json_error_contains(self, result: HttpResponse, msg_substring: str,
                                   status_code: int=400) -> None:
        self.assertIn(msg_substring, self.get_json_error(result, status_code=status_code))

    def assert_in_response(self, substring: str, response: HttpResponse) -> None:
        self.assertIn(substring, response.content.decode('utf-8'))

    def assert_in_success_response(self, substrings: List[str],
                                   response: HttpResponse) -> None:
        self.assertEqual(response.status_code, 200)
        decoded = response.content.decode('utf-8')
        for substring in substrings:
            self.assertIn(substring, decoded)

    def assert_not_in_success_response(self, substrings: List[str],
                                       response: HttpResponse) -> None:
        self.assertEqual(response.status_code, 200)
        decoded = response.content.decode('utf-8')
        for substring in substrings:
            self.assertNotIn(substring, decoded)

    def webhook_fixture_data(self, type: str, action: str, file_type: str='json') -> str:
        fn = os.path.join(
            os.path.dirname(__file__),
            "../webhooks/%s/fixtures/%s.%s" % (type, action, file_type)
        )
        return open(fn).read()

    def fixture_data(self, file_name: str, type: str='') -> str:
        fn = os.path.join(
            os.path.dirname(__file__),
            "../tests/fixtures/%s/%s" % (type, file_name)
        )
        return open(fn).read()

    def make_stream(self, stream_name: str, realm: Optional[Realm]=None,
                    invite_only: Optional[bool]=False,
                    history_public_to_subscribers: Optional[bool]=None) -> Stream:
        if realm is None:
            realm = self.DEFAULT_REALM

        history_public_to_subscribers = get_default_value_for_history_public_to_subscribers(
            realm, invite_only, history_public_to_subscribers)

        try:
            stream = Stream.objects.create(
                realm=realm,
                name=stream_name,
                invite_only=invite_only,
                history_public_to_subscribers=history_public_to_subscribers,
            )
        except IntegrityError:  # nocoverage -- this is for bugs in the tests
            raise Exception('''
                %s already exists

                Please call make_stream with a stream name
                that is not already in use.''' % (stream_name,))

        Recipient.objects.create(type_id=stream.id, type=Recipient.STREAM)
        return stream

    # Subscribe to a stream directly
    def subscribe(self, user_profile: UserProfile, stream_name: str) -> Stream:
        try:
            stream = get_stream(stream_name, user_profile.realm)
            from_stream_creation = False
        except Stream.DoesNotExist:
            stream, from_stream_creation = create_stream_if_needed(user_profile.realm, stream_name)
        bulk_add_subscriptions([stream], [user_profile], from_stream_creation=from_stream_creation)
        return stream

    def unsubscribe(self, user_profile: UserProfile, stream_name: str) -> None:
        client = get_client("website")
        stream = get_stream(stream_name, user_profile.realm)
        bulk_remove_subscriptions([user_profile], [stream], client)

    # Subscribe to a stream by making an API request
    def common_subscribe_to_streams(self, email: str, streams: Iterable[str],
                                    extra_post_data: Dict[str, Any]={}, invite_only: bool=False,
                                    **kwargs: Any) -> HttpResponse:
        post_data = {'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)
        kwargs['realm'] = kwargs.get('subdomain', 'zulip')
        result = self.api_post(email, "/api/v1/users/me/subscriptions", post_data, **kwargs)
        return result

    def check_user_subscribed_only_to_streams(self, user_name: str,
                                              streams: List[Stream]) -> None:
        streams = sorted(streams, key=lambda x: x.name)
        subscribed_streams = gather_subscriptions(self.nonreg_user(user_name))[0]

        self.assertEqual(len(subscribed_streams), len(streams))

        for x, y in zip(subscribed_streams, streams):
            self.assertEqual(x["name"], y.name)

    def send_json_payload(self, user_profile: UserProfile, url: str,
                          payload: Union[str, Dict[str, Any]],
                          stream_name: Optional[str]=None, **post_params: Any) -> Message:
        if stream_name is not None:
            self.subscribe(user_profile, stream_name)

        prior_msg = self.get_last_message()

        result = self.client_post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = self.get_last_message()

        if msg.id == prior_msg.id:
            raise Exception('''
                Your test code called an endpoint that did
                not write any new messages.  It is probably
                broken (but still returns 200 due to exception
                handling).
                ''')  # nocoverage

        self.assertEqual(msg.sender.email, user_profile.email)
        if stream_name is not None:
            self.assertEqual(get_display_recipient(msg.recipient), stream_name)
        # TODO: should also validate recipient for private messages

        return msg

    def get_last_message(self) -> Message:
        return Message.objects.latest('id')

    def get_second_to_last_message(self) -> Message:
        return Message.objects.all().order_by('-id')[1]

    @contextmanager
    def simulated_markdown_failure(self) -> Iterator[None]:
        '''
        This raises a failure inside of the try/except block of
        bugdown.__init__.do_convert.
        '''
        with \
                self.settings(ERROR_BOT=None), \
                mock.patch('zerver.lib.bugdown.timeout', side_effect=KeyError('foo')), \
                mock.patch('zerver.lib.bugdown.bugdown_logger'):
            yield

    def create_default_device(self, user_profile: UserProfile,
                              number: str="+12223334444") -> None:
        phone_device = PhoneDevice(user=user_profile, name='default',
                                   confirmed=True, number=number,
                                   key='abcd', method='sms')
        phone_device.save()

class WebhookTestCase(ZulipTestCase):
    """
    Common for all webhooks tests

    Override below class attributes and run send_and_test_message
    If you create your url in uncommon way you can override build_webhook_url method
    In case that you need modify body or create it without using fixture you can also override get_body method
    """
    STREAM_NAME = None  # type: Optional[str]
    TEST_USER_EMAIL = 'webhook-bot@zulip.com'
    URL_TEMPLATE = None  # type: Optional[str]
    FIXTURE_DIR_NAME = None  # type: Optional[str]

    @property
    def test_user(self) -> UserProfile:
        return get_user(self.TEST_USER_EMAIL, get_realm("zulip"))

    def setUp(self) -> None:
        self.url = self.build_webhook_url()

    def api_stream_message(self, email: str, *args: Any, **kwargs: Any) -> HttpResponse:
        kwargs['HTTP_AUTHORIZATION'] = self.encode_credentials(email)
        return self.send_and_test_stream_message(*args, **kwargs)

    def send_and_test_stream_message(self, fixture_name: str, expected_topic: Optional[str]=None,
                                     expected_message: Optional[str]=None,
                                     content_type: Optional[str]="application/json", **kwargs: Any) -> Message:
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type
        msg = self.send_json_payload(self.test_user, self.url, payload,
                                     self.STREAM_NAME, **kwargs)
        self.do_test_topic(msg, expected_topic)
        self.do_test_message(msg, expected_message)

        return msg

    def send_and_test_private_message(self, fixture_name: str, expected_topic: str=None,
                                      expected_message: str=None, content_type: str="application/json",
                                      **kwargs: Any) -> Message:
        payload = self.get_body(fixture_name)
        if content_type is not None:
            kwargs['content_type'] = content_type

        sender = kwargs.get('sender', self.test_user)
        msg = self.send_json_payload(sender, self.url, payload,
                                     stream_name=None, **kwargs)
        self.do_test_message(msg, expected_message)

        return msg

    def build_webhook_url(self, *args: Any, **kwargs: Any) -> str:
        url = self.URL_TEMPLATE
        if url.find("api_key") >= 0:
            api_key = get_api_key(self.test_user)
            url = self.URL_TEMPLATE.format(api_key=api_key,
                                           stream=self.STREAM_NAME)
        else:
            url = self.URL_TEMPLATE.format(stream=self.STREAM_NAME)

        has_arguments = kwargs or args
        if has_arguments and url.find('?') == -1:
            url = "{}?".format(url)  # nocoverage
        else:
            url = "{}&".format(url)

        for key, value in kwargs.items():
            url = "{}{}={}&".format(url, key, value)

        for arg in args:
            url = "{}{}&".format(url, arg)

        return url[:-1] if has_arguments else url

    def get_body(self, fixture_name: str) -> Union[str, Dict[str, str]]:
        """Can be implemented either as returning a dictionary containing the
        post parameters or as string containing the body of the request."""
        return ujson.dumps(ujson.loads(self.webhook_fixture_data(self.FIXTURE_DIR_NAME, fixture_name)))

    def do_test_topic(self, msg: Message, expected_topic: Optional[str]) -> None:
        if expected_topic is not None:
            self.assertEqual(msg.topic_name(), expected_topic)

    def do_test_message(self, msg: Message, expected_message: Optional[str]) -> None:
        if expected_message is not None:
            self.assertEqual(msg.content, expected_message)

class MigrationsTestCase(ZulipTestCase):
    """
    Test class for database migrations inspired by this blog post:
       https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
    Documented at https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
    """
    @property
    def app(self) -> str:
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None  # type: Optional[str]
    migrate_to = None  # type: Optional[str]

    def setUp(self) -> None:
        assert self.migrate_from and self.migrate_to, \
            "TestCase '{}' must define migrate_from and migrate_to properties".format(type(self).__name__)
        migrate_from = [(self.app, self.migrate_from)]  # type: List[Tuple[str, str]]
        migrate_to = [(self.app, self.migrate_to)]  # type: List[Tuple[str, str]]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(migrate_from).apps

        # Reverse to the original migration
        executor.migrate(migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(migrate_to)

        self.apps = executor.loader.project_state(migrate_to).apps

    def setUpBeforeMigration(self, apps: StateApps) -> None:
        pass  # nocoverage
