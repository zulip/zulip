import time
from typing import Any, Callable, Dict, List, Mapping, Optional
from unittest import mock

import orjson
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from version import API_FEATURE_LEVEL, ZULIP_MERGE_BASE, ZULIP_VERSION
from zerver.actions.custom_profile_fields import try_update_realm_custom_profile_field
from zerver.actions.message_send import check_send_message
from zerver.actions.presence import do_update_user_presence
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.users import do_change_user_role
from zerver.lib.event_schema import check_restart_event
from zerver.lib.events import fetch_initial_state_data
from zerver.lib.exceptions import AccessDeniedError
from zerver.lib.request import RequestVariableMissingError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, dummy_handler, stub_event_queue_user_events
from zerver.lib.users import get_api_key, get_raw_user_data
from zerver.models import (
    CustomProfileField,
    Realm,
    UserMessage,
    UserPresence,
    UserProfile,
    flush_per_request_caches,
    get_client,
    get_realm,
    get_stream,
    get_system_bot,
)
from zerver.tornado.event_queue import (
    allocate_client_descriptor,
    clear_client_event_queues_for_testing,
    get_client_info_for_message_event,
    process_message_event,
    send_restart_events,
)
from zerver.tornado.exceptions import BadEventQueueIdError
from zerver.tornado.views import get_events, get_events_backend
from zerver.views.events_register import (
    _default_all_public_streams,
    _default_narrow,
    events_register_backend,
)


class EventsEndpointTest(ZulipTestCase):
    def test_events_register_without_user_agent(self) -> None:
        result = self.client_post("/json/register", skip_user_agent=True)
        self.assert_json_success(result)

    def test_events_register_endpoint(self) -> None:
        # This test is intended to get minimal coverage on the
        # events_register code paths
        user = self.example_user("hamlet")
        with mock.patch("zerver.views.events_register.do_events_register", return_value={}):
            result = self.api_post(user, "/api/v1/register")
        self.assert_json_success(result)

        with mock.patch("zerver.lib.events.request_event_queue", return_value=None):
            result = self.api_post(user, "/api/v1/register")
        self.assert_json_error(result, "Could not allocate event queue")

        return_event_queue = "15:11"
        return_user_events: List[Dict[str, Any]] = []

        # We choose realm_emoji somewhat randomly--we want
        # a "boring" event type for the purpose of this test.
        event_type = "realm_emoji"
        test_event = dict(id=6, type=event_type, realm_emoji=[])

        # Test that call is made to deal with a returning soft deactivated user.
        with mock.patch("zerver.lib.events.reactivate_user_if_soft_deactivated") as fa:
            with stub_event_queue_user_events(return_event_queue, return_user_events):
                result = self.api_post(
                    user, "/api/v1/register", dict(event_types=orjson.dumps([event_type]).decode())
                )
                self.assertEqual(fa.call_count, 1)

        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.api_post(
                user, "/api/v1/register", dict(event_types=orjson.dumps([event_type]).decode())
            )

        result_dict = self.assert_json_success(result)
        self.assertEqual(result_dict["last_event_id"], -1)
        self.assertEqual(result_dict["queue_id"], "15:11")

        # Now start simulating returning actual data
        return_event_queue = "15:12"
        return_user_events = [test_event]

        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.api_post(
                user, "/api/v1/register", dict(event_types=orjson.dumps([event_type]).decode())
            )

        result_dict = self.assert_json_success(result)
        self.assertEqual(result_dict["last_event_id"], 6)
        self.assertEqual(result_dict["queue_id"], "15:12")

        # sanity check the data relevant to our event
        self.assertEqual(result_dict["realm_emoji"], [])

        # Now test with `fetch_event_types` not matching the event
        return_event_queue = "15:13"
        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.api_post(
                user,
                "/api/v1/register",
                dict(
                    event_types=orjson.dumps([event_type]).decode(),
                    fetch_event_types=orjson.dumps(["message"]).decode(),
                ),
            )
        result_dict = self.assert_json_success(result)
        self.assertEqual(result_dict["last_event_id"], 6)
        # Check that the message event types data is in there
        self.assertIn("max_message_id", result_dict)

        # Check that our original event type is not there.
        self.assertNotIn(event_type, result_dict)
        self.assertEqual(result_dict["queue_id"], "15:13")

        # Now test with `fetch_event_types` matching the event
        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.api_post(
                user,
                "/api/v1/register",
                dict(
                    fetch_event_types=orjson.dumps([event_type]).decode(),
                    event_types=orjson.dumps(["message"]).decode(),
                ),
            )
        result_dict = self.assert_json_success(result)
        self.assertEqual(result_dict["last_event_id"], 6)
        # Check that we didn't fetch the messages data
        self.assertNotIn("max_message_id", result_dict)

        # Check that the realm_emoji data is in there.
        self.assertIn("realm_emoji", result_dict)
        self.assertEqual(result_dict["realm_emoji"], [])
        self.assertEqual(result_dict["queue_id"], "15:13")

    def test_events_register_spectators(self) -> None:
        # Verify that POST /register works for spectators, but not for
        # normal users.
        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            result = self.client_post("/json/register")
            self.assert_json_error(
                result,
                "Not logged in: API authentication or user session required",
                status_code=401,
            )

        result = self.client_post("/json/register")
        result_dict = self.assert_json_success(result)
        self.assertEqual(result_dict["queue_id"], None)
        self.assertEqual(result_dict["realm_uri"], "http://zulip.testserver")

        result = self.client_post("/json/register")
        self.assertEqual(result.status_code, 200)

        result = self.client_post("/json/register", dict(client_gravatar="false"))
        self.assertEqual(result.status_code, 200)

        result = self.client_post("/json/register", dict(client_gravatar="true"))
        self.assert_json_error(
            result,
            "Invalid 'client_gravatar' parameter for anonymous request",
            status_code=400,
        )

        result = self.client_post("/json/register", dict(include_subscribers="true"))
        self.assert_json_error(
            result,
            "Invalid 'include_subscribers' parameter for anonymous request",
            status_code=400,
        )

    def test_events_register_endpoint_all_public_streams_access(self) -> None:
        guest_user = self.example_user("polonius")
        normal_user = self.example_user("hamlet")
        self.assertEqual(guest_user.role, UserProfile.ROLE_GUEST)
        self.assertEqual(normal_user.role, UserProfile.ROLE_MEMBER)

        with mock.patch("zerver.views.events_register.do_events_register", return_value={}):
            result = self.api_post(normal_user, "/api/v1/register", dict(all_public_streams="true"))
        self.assert_json_success(result)

        with mock.patch("zerver.views.events_register.do_events_register", return_value={}):
            result = self.api_post(guest_user, "/api/v1/register", dict(all_public_streams="true"))
        self.assert_json_error(result, "User not authorized for this query")

    def test_events_get_events_endpoint_guest_cant_use_all_public_streams_param(self) -> None:
        """
        This test is meant to execute the very beginning of the codepath
        to ensure guest users are immediately disallowed to use the
        all_public_streams param. Deeper testing is hard (and not necessary for this case)
        due to the codepath expecting AsyncDjangoHandler to be attached to the request,
        which doesn't happen in our test setup.
        """

        guest_user = self.example_user("polonius")
        self.assertEqual(guest_user.role, UserProfile.ROLE_GUEST)

        result = self.api_get(guest_user, "/api/v1/events", dict(all_public_streams="true"))
        self.assert_json_error(result, "User not authorized for this query")

    def test_tornado_endpoint(self) -> None:
        # This test is mostly intended to get minimal coverage on
        # the /notify_tornado endpoint, so we can have 100% URL coverage,
        # but it does exercise a little bit of the codepath.
        post_data = dict(
            data=orjson.dumps(
                dict(
                    event=dict(
                        type="other",
                    ),
                    users=[self.example_user("hamlet").id],
                ),
            ).decode(),
        )
        req = HostRequestMock(post_data)
        req.META["REMOTE_ADDR"] = "127.0.0.1"
        with self.assertRaises(RequestVariableMissingError) as context:
            result = self.client_post_request("/notify_tornado", req)
        self.assertEqual(str(context.exception), "Missing 'secret' argument")
        self.assertEqual(context.exception.http_status_code, 400)

        post_data["secret"] = "random"
        req = HostRequestMock(post_data, user_profile=None)
        req.META["REMOTE_ADDR"] = "127.0.0.1"
        with self.assertRaises(AccessDeniedError) as access_denied_error:
            result = self.client_post_request("/notify_tornado", req)
        self.assertEqual(str(access_denied_error.exception), "Access denied")
        self.assertEqual(access_denied_error.exception.http_status_code, 403)

        post_data["secret"] = settings.SHARED_SECRET
        req = HostRequestMock(post_data, tornado_handler=dummy_handler)
        req.META["REMOTE_ADDR"] = "127.0.0.1"
        result = self.client_post_request("/notify_tornado", req)
        self.assert_json_success(result)

        post_data = dict(secret=settings.SHARED_SECRET)
        req = HostRequestMock(post_data, tornado_handler=dummy_handler)
        req.META["REMOTE_ADDR"] = "127.0.0.1"
        with self.assertRaises(RequestVariableMissingError) as context:
            result = self.client_post_request("/notify_tornado", req)
        self.assertEqual(str(context.exception), "Missing 'data' argument")
        self.assertEqual(context.exception.http_status_code, 400)


class GetEventsTest(ZulipTestCase):
    def tornado_call(
        self,
        view_func: Callable[[HttpRequest, UserProfile], HttpResponse],
        user_profile: UserProfile,
        post_data: Dict[str, Any],
    ) -> HttpResponse:
        request = HostRequestMock(post_data, user_profile, tornado_handler=dummy_handler)
        return view_func(request, user_profile)

    def test_get_events(self) -> None:
        user_profile = self.example_user("hamlet")
        email = user_profile.email
        recipient_user_profile = self.example_user("othello")
        recipient_email = recipient_user_profile.email
        self.login_user(user_profile)

        result = self.tornado_call(
            get_events,
            user_profile,
            {
                "apply_markdown": orjson.dumps(True).decode(),
                "client_gravatar": orjson.dumps(True).decode(),
                "event_types": orjson.dumps(["message"]).decode(),
                "user_client": "website",
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_success(result)
        queue_id = orjson.loads(result.content)["queue_id"]

        recipient_result = self.tornado_call(
            get_events,
            recipient_user_profile,
            {
                "apply_markdown": orjson.dumps(True).decode(),
                "client_gravatar": orjson.dumps(True).decode(),
                "event_types": orjson.dumps(["message"]).decode(),
                "user_client": "website",
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_success(recipient_result)
        recipient_queue_id = orjson.loads(recipient_result.content)["queue_id"]

        result = self.tornado_call(
            get_events,
            user_profile,
            {
                "queue_id": queue_id,
                "user_client": "website",
                "last_event_id": -1,
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        events = orjson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 0)

        local_id = "10.01"
        check_send_message(
            sender=user_profile,
            client=get_client("whatever"),
            message_type_name="private",
            message_to=[recipient_email],
            topic_name=None,
            message_content="hello",
            local_id=local_id,
            sender_queue_id=queue_id,
        )

        result = self.tornado_call(
            get_events,
            user_profile,
            {
                "queue_id": queue_id,
                "user_client": "website",
                "last_event_id": -1,
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        events = orjson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]["type"], "message")
        self.assertEqual(events[0]["message"]["sender_email"], email)
        self.assertEqual(events[0]["local_message_id"], local_id)
        self.assertEqual(events[0]["message"]["display_recipient"][0]["is_mirror_dummy"], False)
        self.assertEqual(events[0]["message"]["display_recipient"][1]["is_mirror_dummy"], False)

        last_event_id = events[0]["id"]
        local_id = "10.02"

        check_send_message(
            sender=user_profile,
            client=get_client("whatever"),
            message_type_name="private",
            message_to=[recipient_email],
            topic_name=None,
            message_content="hello",
            local_id=local_id,
            sender_queue_id=queue_id,
        )

        result = self.tornado_call(
            get_events,
            user_profile,
            {
                "queue_id": queue_id,
                "user_client": "website",
                "last_event_id": last_event_id,
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        events = orjson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]["type"], "message")
        self.assertEqual(events[0]["message"]["sender_email"], email)
        self.assertEqual(events[0]["local_message_id"], local_id)

        # Test that the received message in the receiver's event queue
        # exists and does not contain a local id
        recipient_result = self.tornado_call(
            get_events,
            recipient_user_profile,
            {
                "queue_id": recipient_queue_id,
                "user_client": "website",
                "last_event_id": -1,
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        recipient_events = orjson.loads(recipient_result.content)["events"]
        self.assert_json_success(recipient_result)
        self.assert_length(recipient_events, 2)
        self.assertEqual(recipient_events[0]["type"], "message")
        self.assertEqual(recipient_events[0]["message"]["sender_email"], email)
        self.assertTrue("local_message_id" not in recipient_events[0])
        self.assertEqual(recipient_events[1]["type"], "message")
        self.assertEqual(recipient_events[1]["message"]["sender_email"], email)
        self.assertTrue("local_message_id" not in recipient_events[1])

    def test_get_events_narrow(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)

        def get_message(apply_markdown: bool, client_gravatar: bool) -> Dict[str, Any]:
            result = self.tornado_call(
                get_events,
                user_profile,
                dict(
                    apply_markdown=orjson.dumps(apply_markdown).decode(),
                    client_gravatar=orjson.dumps(client_gravatar).decode(),
                    event_types=orjson.dumps(["message"]).decode(),
                    narrow=orjson.dumps([["stream", "denmark"]]).decode(),
                    user_client="website",
                    dont_block=orjson.dumps(True).decode(),
                ),
            )

            self.assert_json_success(result)
            queue_id = orjson.loads(result.content)["queue_id"]

            result = self.tornado_call(
                get_events,
                user_profile,
                {
                    "queue_id": queue_id,
                    "user_client": "website",
                    "last_event_id": -1,
                    "dont_block": orjson.dumps(True).decode(),
                },
            )
            events = orjson.loads(result.content)["events"]
            self.assert_json_success(result)
            self.assert_length(events, 0)

            self.send_personal_message(user_profile, self.example_user("othello"), "hello")
            self.send_stream_message(user_profile, "Denmark", "**hello**")

            result = self.tornado_call(
                get_events,
                user_profile,
                {
                    "queue_id": queue_id,
                    "user_client": "website",
                    "last_event_id": -1,
                    "dont_block": orjson.dumps(True).decode(),
                },
            )
            events = orjson.loads(result.content)["events"]
            self.assert_json_success(result)
            self.assert_length(events, 1)
            self.assertEqual(events[0]["type"], "message")
            return events[0]["message"]

        message = get_message(apply_markdown=False, client_gravatar=False)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "**hello**")
        self.assertTrue(message["avatar_url"].startswith("https://secure.gravatar.com"))

        message = get_message(apply_markdown=True, client_gravatar=False)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "<p><strong>hello</strong></p>")
        self.assertIn("gravatar.com", message["avatar_url"])

        message = get_message(apply_markdown=False, client_gravatar=True)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "**hello**")
        self.assertEqual(message["avatar_url"], None)

        message = get_message(apply_markdown=True, client_gravatar=True)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "<p><strong>hello</strong></p>")
        self.assertEqual(message["avatar_url"], None)

    def test_bogus_queue_id(self) -> None:
        user = self.example_user("hamlet")

        with self.assertRaises(BadEventQueueIdError):
            self.tornado_call(
                get_events,
                user,
                {
                    "queue_id": "hamster",
                    "user_client": "website",
                    "last_event_id": -1,
                    "dont_block": orjson.dumps(True).decode(),
                },
            )

    def test_wrong_user_queue_id(self) -> None:
        user = self.example_user("hamlet")
        wrong_user = self.example_user("othello")

        result = self.tornado_call(
            get_events,
            user,
            {
                "apply_markdown": orjson.dumps(True).decode(),
                "client_gravatar": orjson.dumps(True).decode(),
                "event_types": orjson.dumps(["message"]).decode(),
                "user_client": "website",
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_success(result)
        queue_id = orjson.loads(result.content)["queue_id"]

        with self.assertLogs(level="WARNING") as cm, self.assertRaises(BadEventQueueIdError):
            self.tornado_call(
                get_events,
                wrong_user,
                {
                    "queue_id": queue_id,
                    "user_client": "website",
                    "last_event_id": -1,
                    "dont_block": orjson.dumps(True).decode(),
                },
            )
        self.assertIn("not authorized for queue", cm.output[0])

    def test_get_events_custom_profile_fields(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        profile_field = CustomProfileField.objects.get(realm=user_profile.realm, name="Pronouns")

        def check_pronouns_type_field_supported(
            pronouns_field_type_supported: bool, new_name: str
        ) -> None:
            clear_client_event_queues_for_testing()

            queue_data = dict(
                apply_markdown=True,
                all_public_streams=True,
                client_type_name="ZulipMobile",
                event_types=["custom_profile_fields"],
                last_connection_time=time.time(),
                queue_timeout=0,
                realm_id=user_profile.realm.id,
                user_profile_id=user_profile.id,
                pronouns_field_type_supported=pronouns_field_type_supported,
            )

            client = allocate_client_descriptor(queue_data)

            try_update_realm_custom_profile_field(
                realm=user_profile.realm, field=profile_field, name=new_name
            )
            result = self.tornado_call(
                get_events,
                user_profile,
                {
                    "queue_id": client.event_queue.id,
                    "user_client": "ZulipAndroid",
                    "last_event_id": -1,
                    "dont_block": orjson.dumps(True).decode(),
                },
            )
            events = orjson.loads(result.content)["events"]
            self.assert_json_success(result)
            self.assert_length(events, 1)

            pronouns_field = [
                field for field in events[0]["fields"] if field["id"] == profile_field.id
            ][0]
            if pronouns_field_type_supported:
                expected_type = CustomProfileField.PRONOUNS
            else:
                expected_type = CustomProfileField.SHORT_TEXT
            self.assertEqual(pronouns_field["type"], expected_type)

        check_pronouns_type_field_supported(False, "Pronouns field")
        check_pronouns_type_field_supported(True, "Pronouns")


class FetchInitialStateDataTest(ZulipTestCase):
    # Non-admin users don't have access to all bots
    def test_realm_bots_non_admin(self) -> None:
        user_profile = self.example_user("cordelia")
        self.assertFalse(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile)
        self.assert_length(result["realm_bots"], 0)

        # additionally the API key for a random bot is not present in the data
        api_key = get_api_key(self.notification_bot(user_profile.realm))
        self.assertNotIn(api_key, str(result))

    # Admin users have access to all bots in the realm_bots field
    def test_realm_bots_admin(self) -> None:
        user_profile = self.example_user("hamlet")
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        self.assertTrue(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile)
        self.assertGreater(len(result["realm_bots"]), 2)

    def test_max_message_id_with_no_history(self) -> None:
        user_profile = self.example_user("aaron")
        # Delete all historical messages for this user
        UserMessage.objects.filter(user_profile=user_profile).delete()
        result = fetch_initial_state_data(user_profile)
        self.assertEqual(result["max_message_id"], -1)

    def test_delivery_email_presence_for_non_admins(self) -> None:
        user_profile = self.example_user("aaron")
        self.assertFalse(user_profile.is_realm_admin)

        do_set_realm_property(
            user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )
        result = fetch_initial_state_data(user_profile)

        for key, value in result["raw_users"].items():
            if key == user_profile.id:
                self.assertEqual(value["delivery_email"], user_profile.delivery_email)
            else:
                self.assertNotIn("delivery_email", value)

        do_set_realm_property(
            user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )
        result = fetch_initial_state_data(user_profile)

        for key, value in result["raw_users"].items():
            if key == user_profile.id:
                self.assertEqual(value["delivery_email"], user_profile.delivery_email)
            else:
                self.assertNotIn("delivery_email", value)

    def test_delivery_email_presence_for_admins(self) -> None:
        user_profile = self.example_user("iago")
        self.assertTrue(user_profile.is_realm_admin)

        do_set_realm_property(
            user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )
        result = fetch_initial_state_data(user_profile)

        for key, value in result["raw_users"].items():
            if key == user_profile.id:
                self.assertEqual(value["delivery_email"], user_profile.delivery_email)
            else:
                self.assertNotIn("delivery_email", value)

        do_set_realm_property(
            user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )
        result = fetch_initial_state_data(user_profile)
        for key, value in result["raw_users"].items():
            self.assertIn("delivery_email", value)

    def test_user_avatar_url_field_optional(self) -> None:
        hamlet = self.example_user("hamlet")
        users = [
            self.example_user("iago"),
            self.example_user("cordelia"),
            self.example_user("ZOE"),
            self.example_user("othello"),
        ]

        for user in users:
            user.long_term_idle = True
            user.save()

        long_term_idle_users_ids = [user.id for user in users]

        result = fetch_initial_state_data(
            user_profile=hamlet,
            user_avatar_url_field_optional=True,
        )

        raw_users = result["raw_users"]

        for user_dict in raw_users.values():
            if user_dict["user_id"] in long_term_idle_users_ids:
                self.assertFalse("avatar_url" in user_dict)
            else:
                self.assertIsNotNone(user_dict["avatar_url"])

        gravatar_users_id = [
            user_dict["user_id"]
            for user_dict in raw_users.values()
            if "avatar_url" in user_dict and "gravatar.com" in user_dict["avatar_url"]
        ]

        # Test again with client_gravatar = True
        result = fetch_initial_state_data(
            user_profile=hamlet,
            client_gravatar=True,
            user_avatar_url_field_optional=True,
        )

        raw_users = result["raw_users"]

        for user_dict in raw_users.values():
            if user_dict["user_id"] in gravatar_users_id:
                self.assertIsNone(user_dict["avatar_url"])
            else:
                self.assertFalse("avatar_url" in user_dict)

    def test_user_settings_based_on_client_capabilities(self) -> None:
        hamlet = self.example_user("hamlet")
        result = fetch_initial_state_data(
            user_profile=hamlet,
            user_settings_object=True,
        )
        self.assertIn("user_settings", result)
        for prop in UserProfile.property_types:
            self.assertNotIn(prop, result)
            self.assertIn(prop, result["user_settings"])

        result = fetch_initial_state_data(
            user_profile=hamlet,
            user_settings_object=False,
        )
        self.assertIn("user_settings", result)
        for prop in UserProfile.property_types:
            if prop in {
                **UserProfile.display_settings_legacy,
                **UserProfile.notification_settings_legacy,
            }:
                # Only legacy settings are included in the top level.
                self.assertIn(prop, result)
            self.assertIn(prop, result["user_settings"])

    def test_pronouns_field_type_support(self) -> None:
        hamlet = self.example_user("hamlet")
        result = fetch_initial_state_data(
            user_profile=hamlet,
            pronouns_field_type_supported=False,
        )
        self.assertIn("custom_profile_fields", result)
        custom_profile_fields = result["custom_profile_fields"]
        pronouns_field = [field for field in custom_profile_fields if field["name"] == "Pronouns"][
            0
        ]
        self.assertEqual(pronouns_field["type"], CustomProfileField.SHORT_TEXT)

        result = fetch_initial_state_data(
            user_profile=hamlet,
            pronouns_field_type_supported=True,
        )
        self.assertIn("custom_profile_fields", result)
        custom_profile_fields = result["custom_profile_fields"]
        pronouns_field = [field for field in custom_profile_fields if field["name"] == "Pronouns"][
            0
        ]
        self.assertEqual(pronouns_field["type"], CustomProfileField.PRONOUNS)


class ClientDescriptorsTest(ZulipTestCase):
    def test_get_client_info_for_all_public_streams(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name="website",
            event_types=["message"],
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )

        client = allocate_client_descriptor(queue_data)

        message_event = dict(
            realm_id=realm.id,
            stream_name="whatever",
        )

        client_info = get_client_info_for_message_event(
            message_event,
            users=[],
        )

        self.assert_length(client_info, 1)

        dct = client_info[client.event_queue.id]
        self.assertEqual(dct["client"].apply_markdown, True)
        self.assertEqual(dct["client"].client_gravatar, True)
        self.assertEqual(dct["client"].user_profile_id, hamlet.id)
        self.assertEqual(dct["flags"], [])
        self.assertEqual(dct["is_sender"], False)

        message_event = dict(
            realm_id=realm.id,
            stream_name="whatever",
            sender_queue_id=client.event_queue.id,
        )

        client_info = get_client_info_for_message_event(
            message_event,
            users=[],
        )
        dct = client_info[client.event_queue.id]
        self.assertEqual(dct["is_sender"], True)

    def test_get_client_info_for_normal_users(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm

        def test_get_info(apply_markdown: bool, client_gravatar: bool) -> None:
            clear_client_event_queues_for_testing()

            queue_data = dict(
                all_public_streams=False,
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
                client_type_name="website",
                event_types=["message"],
                last_connection_time=time.time(),
                queue_timeout=0,
                realm_id=realm.id,
                user_profile_id=hamlet.id,
            )

            client = allocate_client_descriptor(queue_data)
            message_event = dict(
                realm_id=realm.id,
                stream_name="whatever",
            )

            client_info = get_client_info_for_message_event(
                message_event,
                users=[
                    dict(id=cordelia.id),
                ],
            )

            self.assert_length(client_info, 0)

            client_info = get_client_info_for_message_event(
                message_event,
                users=[
                    dict(id=cordelia.id),
                    dict(id=hamlet.id, flags=["mentioned"]),
                ],
            )
            self.assert_length(client_info, 1)

            dct = client_info[client.event_queue.id]
            self.assertEqual(dct["client"].apply_markdown, apply_markdown)
            self.assertEqual(dct["client"].client_gravatar, client_gravatar)
            self.assertEqual(dct["client"].user_profile_id, hamlet.id)
            self.assertEqual(dct["flags"], ["mentioned"])
            self.assertEqual(dct["is_sender"], False)

        test_get_info(apply_markdown=False, client_gravatar=False)
        test_get_info(apply_markdown=True, client_gravatar=False)

        test_get_info(apply_markdown=False, client_gravatar=True)
        test_get_info(apply_markdown=True, client_gravatar=True)

    def test_process_message_event_with_mocked_client_info(self) -> None:
        hamlet = self.example_user("hamlet")

        class MockClient:
            def __init__(
                self, user_profile_id: int, apply_markdown: bool, client_gravatar: bool
            ) -> None:
                self.user_profile_id = user_profile_id
                self.apply_markdown = apply_markdown
                self.client_gravatar = client_gravatar
                self.client_type_name = "whatever"
                self.events: List[Dict[str, Any]] = []

            def accepts_messages(self) -> bool:
                return True

            def accepts_event(self, event: Dict[str, Any]) -> bool:
                assert event["type"] == "message"
                return True

            def add_event(self, event: Dict[str, Any]) -> None:
                self.events.append(event)

        client1 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=True,
            client_gravatar=False,
        )

        client2 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=False,
            client_gravatar=False,
        )

        client3 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=True,
            client_gravatar=True,
        )

        client4 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=False,
            client_gravatar=True,
        )

        client_info = {
            "client:1": dict(
                client=client1,
                flags=["starred"],
            ),
            "client:2": dict(
                client=client2,
                flags=["has_alert_word"],
            ),
            "client:3": dict(
                client=client3,
                flags=[],
            ),
            "client:4": dict(
                client=client4,
                flags=[],
            ),
        }

        sender = hamlet

        message_event = dict(
            message_dict=dict(
                id=999,
                content="**hello**",
                rendered_content="<b>hello</b>",
                sender_id=sender.id,
                type="stream",
                client="website",
                # NOTE: Some of these fields are clutter, but some
                #       will be useful when we let clients specify
                #       that they can compute their own gravatar URLs.
                sender_email=sender.email,
                sender_delivery_email=sender.delivery_email,
                sender_realm_id=sender.realm_id,
                sender_avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
                sender_avatar_version=1,
                sender_is_mirror_dummy=None,
                recipient_type=None,
                recipient_type_id=None,
            ),
        )

        # Setting users to `[]` bypasses code we don't care about
        # for this test--we assume client_info is correct in our mocks,
        # and we are interested in how messages are put on event queue.
        users: List[Dict[str, Any]] = []

        with mock.patch(
            "zerver.tornado.event_queue.get_client_info_for_message_event", return_value=client_info
        ):
            process_message_event(message_event, users)

        # We are not closely examining avatar_url at this point, so
        # just sanity check them and then delete the keys so that
        # upcoming comparisons work.
        for client in [client1, client2]:
            message = client.events[0]["message"]
            self.assertIn("gravatar.com", message["avatar_url"])
            message.pop("avatar_url")

        self.assertEqual(
            client1.events,
            [
                dict(
                    type="message",
                    message=dict(
                        type="stream",
                        sender_id=sender.id,
                        sender_email=sender.email,
                        id=999,
                        content="<b>hello</b>",
                        content_type="text/html",
                        client="website",
                    ),
                    flags=["starred"],
                ),
            ],
        )

        self.assertEqual(
            client2.events,
            [
                dict(
                    type="message",
                    message=dict(
                        type="stream",
                        sender_id=sender.id,
                        sender_email=sender.email,
                        id=999,
                        content="**hello**",
                        content_type="text/x-markdown",
                        client="website",
                    ),
                    flags=["has_alert_word"],
                ),
            ],
        )

        self.assertEqual(
            client3.events,
            [
                dict(
                    type="message",
                    message=dict(
                        type="stream",
                        sender_id=sender.id,
                        sender_email=sender.email,
                        avatar_url=None,
                        id=999,
                        content="<b>hello</b>",
                        content_type="text/html",
                        client="website",
                    ),
                    flags=[],
                ),
            ],
        )

        self.assertEqual(
            client4.events,
            [
                dict(
                    type="message",
                    message=dict(
                        type="stream",
                        sender_id=sender.id,
                        sender_email=sender.email,
                        avatar_url=None,
                        id=999,
                        content="**hello**",
                        content_type="text/x-markdown",
                        client="website",
                    ),
                    flags=[],
                ),
            ],
        )


class RestartEventsTest(ZulipTestCase):
    def tornado_call(
        self,
        view_func: Callable[[HttpRequest, UserProfile], HttpResponse],
        user_profile: UserProfile,
        post_data: Dict[str, Any],
        client_name: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> HttpResponse:
        meta_data: Optional[Dict[str, Any]] = None
        if user_agent is not None:
            meta_data = {"HTTP_USER_AGENT": user_agent}

        request = HostRequestMock(
            post_data,
            user_profile,
            client_name=client_name,
            tornado_handler=dummy_handler,
            meta_data=meta_data,
        )
        return view_func(request, user_profile)

    def test_restart(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        clear_client_event_queues_for_testing()

        queue_data = dict(
            all_public_streams=False,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name="website",
            event_types=None,
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )
        client = allocate_client_descriptor(queue_data)

        send_restart_events(immediate=True)

        # For now we only verify that a virtual event
        # gets added to the client's event_queue.  We
        # may decide to write a deeper test in the future
        # that exercises the finish_handler.
        virtual_events = client.event_queue.virtual_events
        self.assert_length(virtual_events, 1)
        restart_event = virtual_events["restart"]

        check_restart_event("restart_event", restart_event)
        self.assertEqual(
            restart_event,
            dict(
                type="restart",
                zulip_version=ZULIP_VERSION,
                zulip_merge_base=ZULIP_MERGE_BASE,
                zulip_feature_level=API_FEATURE_LEVEL,
                server_generation=settings.SERVER_GENERATION,
                immediate=True,
                id=0,
            ),
        )

    def test_restart_event_recursive_call_logic(self) -> None:
        # This is a test for a subtle corner case; see the comments
        # around RestartEventError for details.
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        # Set up an empty event queue
        clear_client_event_queues_for_testing()

        queue_data = dict(
            all_public_streams=False,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name="website",
            event_types=None,
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )
        client = allocate_client_descriptor(queue_data)

        # Add a restart event to it.
        send_restart_events(immediate=True)

        # Make a second queue after the restart events were sent.
        second_client = allocate_client_descriptor(queue_data)

        # Fetch the restart event just sent above, without removing it
        # from the queue. We will use this as a mock return value in
        # get_user_events.
        restart_event = orjson.loads(
            self.tornado_call(
                get_events_backend,
                hamlet,
                post_data={
                    "queue_id": client.event_queue.id,
                    "last_event_id": -1,
                    "dont_block": "true",
                    "user_profile_id": hamlet.id,
                    "secret": settings.SHARED_SECRET,
                    "client": "internal",
                },
                client_name="internal",
            ).content
        )["events"]

        # Now the tricky part: We call events_register_backend,
        # arranging it so that the first `get_user_events` call
        # returns our restart event (triggering the recursive
        # behavior), but the second (with a new queue) returns no
        # events.
        #
        # Because get_user_events always returns [] in tests, we need
        # to mock its return value as well; in an ideal world, we
        # would only need to mock client / second_client.
        with mock.patch(
            "zerver.lib.events.request_event_queue",
            side_effect=[client.event_queue.id, second_client.event_queue.id],
        ), mock.patch("zerver.lib.events.get_user_events", side_effect=[restart_event, []]):
            self.tornado_call(
                events_register_backend,
                hamlet,
                {
                    "queue_id": client.event_queue.id,
                    "user_client": "website",
                    "last_event_id": -1,
                    "dont_block": orjson.dumps(True).decode(),
                },
                client_name="website",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            )


class FetchQueriesTest(ZulipTestCase):
    def test_queries(self) -> None:
        user = self.example_user("hamlet")

        self.login_user(user)

        flush_per_request_caches()
        with self.assert_database_query_count(37):
            with mock.patch("zerver.lib.events.always_want") as want_mock:
                fetch_initial_state_data(user)

        expected_counts = dict(
            alert_words=1,
            custom_profile_fields=1,
            default_streams=1,
            default_stream_groups=1,
            drafts=1,
            hotspots=0,
            message=1,
            muted_topics=1,
            muted_users=1,
            presence=1,
            realm=0,
            realm_bot=1,
            realm_domains=1,
            realm_embedded_bots=0,
            realm_incoming_webhook_bots=0,
            realm_emoji=1,
            realm_filters=1,
            realm_linkifiers=1,
            realm_playgrounds=1,
            realm_user=3,
            realm_user_groups=3,
            realm_user_settings_defaults=1,
            recent_private_conversations=1,
            starred_messages=1,
            stream=2,
            stop_words=0,
            subscription=4,
            update_display_settings=0,
            update_global_notifications=0,
            update_message_flags=5,
            user_settings=0,
            user_status=1,
            user_topic=1,
            video_calls=0,
            giphy=0,
        )

        wanted_event_types = {item[0][0] for item in want_mock.call_args_list}

        self.assertEqual(wanted_event_types, set(expected_counts))

        for event_type in sorted(wanted_event_types):
            count = expected_counts[event_type]
            flush_per_request_caches()
            with self.assert_database_query_count(count):
                if event_type == "update_message_flags":
                    event_types = ["update_message_flags", "message"]
                else:
                    event_types = [event_type]

                fetch_initial_state_data(user, event_types=event_types)


class TestEventsRegisterAllPublicStreamsDefaults(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")
        self.email = self.user_profile.email

    def test_use_passed_all_public_true_default_false(self) -> None:
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, True)
        self.assertTrue(result)

    def test_use_passed_all_public_true_default(self) -> None:
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, True)
        self.assertTrue(result)

    def test_use_passed_all_public_false_default_false(self) -> None:
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, False)
        self.assertFalse(result)

    def test_use_passed_all_public_false_default_true(self) -> None:
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, False)
        self.assertFalse(result)

    def test_use_true_default_for_none(self) -> None:
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, None)
        self.assertTrue(result)

    def test_use_false_default_for_none(self) -> None:
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, None)
        self.assertFalse(result)


class TestEventsRegisterNarrowDefaults(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")
        self.email = self.user_profile.email
        self.stream = get_stream("Verona", self.user_profile.realm)

    def test_use_passed_narrow_no_default(self) -> None:
        self.user_profile.default_events_register_stream_id = None
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [["stream", "my_stream"]])
        self.assertEqual(result, [["stream", "my_stream"]])

    def test_use_passed_narrow_with_default(self) -> None:
        self.user_profile.default_events_register_stream_id = self.stream.id
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [["stream", "my_stream"]])
        self.assertEqual(result, [["stream", "my_stream"]])

    def test_use_default_if_narrow_is_empty(self) -> None:
        self.user_profile.default_events_register_stream_id = self.stream.id
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [])
        self.assertEqual(result, [["stream", "Verona"]])

    def test_use_narrow_if_default_is_none(self) -> None:
        self.user_profile.default_events_register_stream_id = None
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [])
        self.assertEqual(result, [])


class TestGetRawUserDataSystemBotRealm(ZulipTestCase):
    def test_get_raw_user_data_on_system_bot_realm(self) -> None:
        realm = get_realm(settings.SYSTEM_BOT_REALM)
        result = get_raw_user_data(
            realm,
            self.example_user("hamlet"),
            client_gravatar=True,
            user_avatar_url_field_optional=True,
        )

        for bot_email in settings.CROSS_REALM_BOT_EMAILS:
            bot_profile = get_system_bot(bot_email, realm.id)
            self.assertTrue(bot_profile.id in result)
            self.assertTrue(result[bot_profile.id]["is_system_bot"])


class TestUserPresenceUpdatesDisabled(ZulipTestCase):
    # For this test, we verify do_update_user_presence doesn't send
    # events for organizations with more than
    # USER_LIMIT_FOR_SENDING_PRESENCE_UPDATE_EVENTS users, unless
    # force_send_update is passed.
    @override_settings(USER_LIMIT_FOR_SENDING_PRESENCE_UPDATE_EVENTS=3)
    def test_presence_events_disabled_on_larger_realm(self) -> None:
        events: List[Mapping[str, Any]] = []
        with self.tornado_redirected_to_list(events, expected_num_events=1):
            do_update_user_presence(
                self.example_user("cordelia"),
                get_client("website"),
                timezone_now(),
                UserPresence.ACTIVE,
                force_send_update=True,
            )

        with self.tornado_redirected_to_list(events, expected_num_events=0):
            do_update_user_presence(
                self.example_user("hamlet"),
                get_client("website"),
                timezone_now(),
                UserPresence.ACTIVE,
                force_send_update=False,
            )
