import orjson

from zerver.lib.subscription_info import gather_subscriptions, gather_subscriptions_helper
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_subscription
from zerver.models import Recipient, Subscription


class SubscriptionPropertiesTest(ZulipTestCase):
    def test_set_stream_color(self) -> None:
        """
        A POST request to /api/v1/users/me/subscriptions/properties with stream_id and
        color data sets the stream color, and for that stream only. Also, make sure that
        any invalid hex color codes are bounced.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        old_subs, _ = gather_subscriptions(test_user)
        sub = old_subs[0]
        stream_id = sub["stream_id"]
        new_color = "#ffffff"  # TODO: ensure that this is different from old_color
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "color", "stream_id": stream_id, "value": "#ffffff"}]
                ).decode()
            },
        )
        self.assert_json_success(result)

        new_subs = gather_subscriptions(test_user)[0]
        found_sub = None
        for sub in new_subs:
            if sub["stream_id"] == stream_id:
                found_sub = sub
                break

        assert found_sub is not None
        self.assertEqual(found_sub["color"], new_color)

        new_subs.remove(found_sub)
        for sub in old_subs:
            if sub["stream_id"] == stream_id:
                found_sub = sub
                break
        old_subs.remove(found_sub)
        self.assertEqual(old_subs, new_subs)

        invalid_color = "3ffrff"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "color", "stream_id": stream_id, "value": invalid_color}]
                ).decode()
            },
        )
        self.assert_json_error(
            result, "Invalid subscription_data[0]: Value error, color is not a valid hex color code"
        )

    def test_set_color_missing_stream_id(self) -> None:
        """
        Updating the color property requires a `stream_id` key.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "color", "value": "#ffffff"}]
                ).decode()
            },
        )
        self.assert_json_error(
            result, 'subscription_data[0]["stream_id"] field is missing: Field required'
        )

    def test_set_color_unsubscribed_stream_id(self) -> None:
        """
        Updating the color property requires a subscribed stream.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        sub_info = gather_subscriptions_helper(test_user)

        not_subbed = sub_info.never_subscribed

        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [
                        {
                            "property": "color",
                            "stream_id": not_subbed[0]["stream_id"],
                            "value": "#ffffff",
                        }
                    ]
                ).decode()
            },
        )
        self.assert_json_error(
            result, "Not subscribed to channel ID {}".format(not_subbed[0]["stream_id"])
        )

    def test_set_color_missing_color(self) -> None:
        """
        Updating the color property requires a color.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "color", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(
            result, 'subscription_data[0]["value"] field is missing: Field required'
        )

    def test_set_stream_wildcard_mentions_notify(self) -> None:
        """
        A POST request to /api/v1/users/me/subscriptions/properties with wildcard_mentions_notify
        sets the property.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        subs = gather_subscriptions(test_user)[0]
        sub = subs[0]
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [
                        {
                            "property": "wildcard_mentions_notify",
                            "stream_id": sub["stream_id"],
                            "value": True,
                        }
                    ]
                ).decode()
            },
        )

        self.assert_json_success(result)

        updated_sub = get_subscription(sub["name"], test_user)
        self.assertIsNotNone(updated_sub)
        self.assertEqual(updated_sub.wildcard_mentions_notify, True)

    def test_set_pin_to_top(self) -> None:
        """
        A POST request to /api/v1/users/me/subscriptions/properties with stream_id and
        pin_to_top data pins the stream.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        old_subs, _ = gather_subscriptions(user)
        sub = old_subs[0]
        stream_id = sub["stream_id"]
        new_pin_to_top = not sub["pin_to_top"]
        result = self.api_post(
            user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "pin_to_top", "stream_id": stream_id, "value": new_pin_to_top}]
                ).decode()
            },
        )
        self.assert_json_success(result)

        updated_sub = get_subscription(sub["name"], user)

        self.assertIsNotNone(updated_sub)
        self.assertEqual(updated_sub.pin_to_top, new_pin_to_top)

    def test_change_is_muted(self) -> None:
        test_user = self.example_user("hamlet")
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]

        sub = Subscription.objects.get(
            recipient__type=Recipient.STREAM,
            recipient__type_id=subs[0]["stream_id"],
            user_profile=test_user,
        )
        self.assertEqual(sub.is_muted, False)

        property_name = "is_muted"
        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.api_post(
                test_user,
                "/api/v1/users/me/subscriptions/properties",
                {
                    "subscription_data": orjson.dumps(
                        [
                            {
                                "property": property_name,
                                "value": True,
                                "stream_id": subs[0]["stream_id"],
                            }
                        ]
                    ).decode()
                },
            )
        self.assert_json_success(result)
        self.assertEqual(events[0]["event"]["property"], "in_home_view")
        self.assertEqual(events[0]["event"]["value"], False)
        self.assertEqual(events[1]["event"]["property"], "is_muted")
        self.assertEqual(events[1]["event"]["value"], True)
        sub = Subscription.objects.get(
            recipient__type=Recipient.STREAM,
            recipient__type_id=subs[0]["stream_id"],
            user_profile=test_user,
        )
        self.assertEqual(sub.is_muted, True)

        legacy_property_name = "in_home_view"
        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.api_post(
                test_user,
                "/api/v1/users/me/subscriptions/properties",
                {
                    "subscription_data": orjson.dumps(
                        [
                            {
                                "property": legacy_property_name,
                                "value": True,
                                "stream_id": subs[0]["stream_id"],
                            }
                        ]
                    ).decode()
                },
            )
        self.assert_json_success(result)
        self.assertEqual(events[0]["event"]["property"], "in_home_view")
        self.assertEqual(events[0]["event"]["value"], True)
        self.assertEqual(events[1]["event"]["property"], "is_muted")
        self.assertEqual(events[1]["event"]["value"], False)
        self.assert_json_success(result)
        sub = Subscription.objects.get(
            recipient__type=Recipient.STREAM,
            recipient__type_id=subs[0]["stream_id"],
            user_profile=test_user,
        )
        self.assertEqual(sub.is_muted, False)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.api_post(
                test_user,
                "/api/v1/users/me/subscriptions/properties",
                {
                    "subscription_data": orjson.dumps(
                        [
                            {
                                "property": legacy_property_name,
                                "value": False,
                                "stream_id": subs[0]["stream_id"],
                            }
                        ]
                    ).decode()
                },
            )
        self.assert_json_success(result)
        self.assertEqual(events[0]["event"]["property"], "in_home_view")
        self.assertEqual(events[0]["event"]["value"], False)
        self.assertEqual(events[1]["event"]["property"], "is_muted")
        self.assertEqual(events[1]["event"]["value"], True)

        sub = Subscription.objects.get(
            recipient__type=Recipient.STREAM,
            recipient__type_id=subs[0]["stream_id"],
            user_profile=test_user,
        )
        self.assertEqual(sub.is_muted, True)

    def test_set_subscription_property_incorrect(self) -> None:
        """
        Trying to set a property incorrectly returns a JSON error.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]

        property_name = "is_muted"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "in_home_view"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "desktop_notifications"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "audible_notifications"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "push_notifications"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "email_notifications"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "wildcard_mentions_notify"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )

        self.assert_json_error(result, f"{property_name} is not a boolean")

        property_name = "color"
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": property_name, "value": False, "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(
            result, "Invalid subscription_data[0]: Value error, color is not a valid hex color code"
        )

    def test_json_subscription_property_invalid_stream(self) -> None:
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        stream_id = 1000
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "is_muted", "stream_id": stream_id, "value": False}]
                ).decode()
            },
        )
        self.assert_json_error(result, "Invalid channel ID")

    def test_set_invalid_property(self) -> None:
        """
        Trying to set an invalid property returns a JSON error.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [{"property": "bad", "value": "bad", "stream_id": subs[0]["stream_id"]}]
                ).decode()
            },
        )
        self.assert_json_error(result, "Unknown subscription property: bad")

    def test_ignored_parameters_in_subscriptions_properties_endpoint(self) -> None:
        """
        Sending an invalid parameter with a valid parameter returns
        an `ignored_parameters_unsupported` array.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        subs = gather_subscriptions(test_user)[0]
        sub = subs[0]
        result = self.api_post(
            test_user,
            "/api/v1/users/me/subscriptions/properties",
            {
                "subscription_data": orjson.dumps(
                    [
                        {
                            "property": "wildcard_mentions_notify",
                            "stream_id": sub["stream_id"],
                            "value": True,
                        }
                    ]
                ).decode(),
                "invalid_parameter": orjson.dumps(
                    [{"property": "pin_to_top", "stream_id": sub["stream_id"], "value": False}]
                ).decode(),
            },
        )

        self.assert_json_success(result, ignored_parameters=["invalid_parameter"])
