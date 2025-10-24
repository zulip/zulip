import orjson

from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_change_realm_plan_type,
    do_set_realm_property,
)
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.users import do_change_user_role
from zerver.lib.default_streams import get_default_stream_ids_for_realm
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import UnreadStreamInfo, aggregate_unread_data, get_raw_unread_data
from zerver.lib.streams import (
    StreamDict,
    create_stream_if_needed,
    create_streams_if_needed,
    ensure_stream,
    list_to_streams,
)
from zerver.lib.test_classes import ZulipTestCase, get_topic_messages
from zerver.lib.test_helpers import reset_email_visibility_to_everyone_in_zulip_realm
from zerver.lib.types import UserGroupMembersData, UserGroupMembersDict
from zerver.models import (
    Message,
    NamedUserGroup,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import StreamTopicsPolicyEnum, get_stream
from zerver.models.users import active_non_guest_user_ids


class TestCreateStreams(ZulipTestCase):
    def test_creating_streams(self) -> None:
        stream_names = ["new1", "new2", "new3"]
        stream_descriptions = ["des1", "des2", "des3"]
        realm = get_realm("zulip")
        iago = self.example_user("iago")

        # Test stream creation events.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            ensure_stream(realm, "Public stream", invite_only=False, acting_user=None)

        self.assertEqual(events[0]["event"]["type"], "stream")
        self.assertEqual(events[0]["event"]["op"], "create")
        # Send public stream creation event to all active users.
        self.assertEqual(events[0]["users"], active_non_guest_user_ids(realm.id))
        self.assertEqual(events[0]["event"]["streams"][0]["name"], "Public stream")
        self.assertEqual(events[0]["event"]["streams"][0]["stream_weekly_traffic"], None)

        aaron_group = check_add_user_group(
            realm, "aaron_group", [self.example_user("aaron")], acting_user=iago
        )
        prospero_group = check_add_user_group(
            realm, "prospero_group", [self.example_user("prospero")], acting_user=iago
        )
        cordelia_group = check_add_user_group(
            realm, "cordelia_group", [self.example_user("cordelia")], acting_user=iago
        )
        with self.capture_send_event_calls(expected_num_events=1) as events:
            create_stream_if_needed(
                realm,
                "Private stream",
                invite_only=True,
                can_administer_channel_group=aaron_group,
                can_add_subscribers_group=prospero_group,
                can_subscribe_group=cordelia_group,
            )

        self.assertEqual(events[0]["event"]["type"], "stream")
        self.assertEqual(events[0]["event"]["op"], "create")
        # Send private stream creation event to only realm admins.
        self.assert_length(events[0]["users"], 5)
        self.assertCountEqual(
            [
                iago.id,
                self.example_user("desdemona").id,
                self.example_user("aaron").id,
                self.example_user("prospero").id,
                self.example_user("cordelia").id,
            ],
            events[0]["users"],
        )
        self.assertEqual(events[0]["event"]["streams"][0]["name"], "Private stream")
        self.assertEqual(events[0]["event"]["streams"][0]["stream_weekly_traffic"], None)

        moderators_system_group = NamedUserGroup.objects.get(
            name="role:moderators", realm_for_sharding=realm, is_system_group=True
        )
        new_streams, existing_streams = create_streams_if_needed(
            realm,
            [
                {
                    "name": stream_name,
                    "description": stream_description,
                    "invite_only": True,
                    "message_retention_days": -1,
                    "can_remove_subscribers_group": moderators_system_group,
                }
                for (stream_name, stream_description) in zip(
                    stream_names, stream_descriptions, strict=False
                )
            ],
        )

        self.assert_length(new_streams, 3)
        self.assert_length(existing_streams, 0)

        actual_stream_names = {stream.name for stream in new_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in new_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in new_streams:
            self.assertTrue(stream.invite_only)
            self.assertTrue(stream.message_retention_days == -1)
            self.assertEqual(stream.can_remove_subscribers_group.id, moderators_system_group.id)
            # Streams created where acting_user is None have no creator
            self.assertIsNone(stream.creator_id)

        new_streams, existing_streams = create_streams_if_needed(
            realm,
            [
                {"name": stream_name, "description": stream_description, "invite_only": True}
                for (stream_name, stream_description) in zip(
                    stream_names, stream_descriptions, strict=False
                )
            ],
        )

        self.assert_length(new_streams, 0)
        self.assert_length(existing_streams, 3)

        actual_stream_names = {stream.name for stream in existing_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in existing_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in existing_streams:
            self.assertTrue(stream.invite_only)

    def test_create_api_multiline_description(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        subscriptions = [{"name": "new_stream", "description": "multi\nline\ndescription"}]
        result = self.subscribe_via_post(user, subscriptions, subdomain="zulip")
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(stream.description, "multi line description")

    def test_create_api_topic_permalink_description(self) -> None:
        user = self.example_user("iago")
        realm = user.realm
        self.login_user(user)

        hamlet = self.example_user("hamlet")
        core_stream = self.make_stream("core", realm, True, history_public_to_subscribers=True)
        self.subscribe(hamlet, "core")
        msg_id = self.send_stream_message(hamlet, "core", topic_name="testing")

        # Test permalink not generated for description since user has no access to
        # the channel.
        subscriptions = [{"name": "stream1", "description": "#**core>testing**"}]
        result = self.subscribe_via_post(user, subscriptions, subdomain="zulip")
        self.assert_json_success(result)
        stream = get_stream("stream1", realm)

        self.assertEqual(stream.rendered_description, "<p>#<strong>core&gt;testing</strong></p>")

        self.subscribe(user, "core")

        # Test permalink generated for the description since user now has access
        # to the channel.
        subscriptions = [{"name": "stream2", "description": "#**core>testing**"}]
        result = self.subscribe_via_post(user, subscriptions, subdomain="zulip")
        self.assert_json_success(result)
        stream = get_stream("stream2", realm)

        self.assertEqual(
            stream.rendered_description,
            f'<p><a class="stream-topic" data-stream-id="{core_stream.id}" href="/#narrow/channel/{core_stream.id}-core/topic/testing/with/{msg_id}">#{core_stream.name} &gt; testing</a></p>',
        )

    def test_history_public_to_subscribers_on_stream_creation(self) -> None:
        realm = get_realm("zulip")
        stream_dicts: list[StreamDict] = [
            {
                "name": "publicstream",
                "description": "Public stream with public history",
            },
            {"name": "webpublicstream", "description": "Web-public stream", "is_web_public": True},
            {
                "name": "privatestream",
                "description": "Private stream with non-public history",
                "invite_only": True,
            },
            {
                "name": "privatewithhistory",
                "description": "Private stream with public history",
                "invite_only": True,
                "history_public_to_subscribers": True,
            },
            {
                "name": "publictrywithouthistory",
                "description": "Public stream without public history (disallowed)",
                "invite_only": False,
                "history_public_to_subscribers": False,
            },
        ]

        created, existing = create_streams_if_needed(realm, stream_dicts)

        self.assert_length(created, 5)
        self.assert_length(existing, 0)
        for stream in created:
            if stream.name == "publicstream":
                self.assertTrue(stream.history_public_to_subscribers)
            if stream.name == "webpublicstream":
                self.assertTrue(stream.history_public_to_subscribers)
            if stream.name == "privatestream":
                self.assertFalse(stream.history_public_to_subscribers)
            if stream.name == "privatewithhistory":
                self.assertTrue(stream.history_public_to_subscribers)
            if stream.name == "publictrywithouthistory":
                self.assertTrue(stream.history_public_to_subscribers)

    def test_add_stream_as_default_on_stream_creation(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm

        subscriptions = [
            {"name": "default_stream", "description": "This stream is default for new users"}
        ]
        result = self.subscribe_via_post(
            user_profile,
            subscriptions,
            {"is_default_stream": "true"},
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.subscribe_via_post(
            user_profile, subscriptions, {"is_default_stream": "true"}, subdomain="zulip"
        )
        self.assert_json_success(result)
        default_stream = get_stream("default_stream", realm)
        self.assertTrue(default_stream.id in get_default_stream_ids_for_realm(realm.id))

        subscriptions = [
            {
                "name": "private_default_stream",
                "description": "This stream is private and default for new users",
            }
        ]
        result = self.subscribe_via_post(
            user_profile,
            subscriptions,
            {"is_default_stream": "true"},
            invite_only=True,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_error(result, "A default channel cannot be private.")

    def test_create_stream_using_add_channel(self) -> None:
        user_profile = self.example_user("iago")
        result = self.create_channel_via_post(user_profile, name="basketball")
        self.assert_json_success(result)
        stream = get_stream("basketball", user_profile.realm)
        self.assertEqual(stream.name, "basketball")

        cordelia = self.example_user("cordelia")
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=cordelia.realm, is_system_group=True
        )

        channel_folder = check_add_channel_folder(
            user_profile.realm, "sports", "", acting_user=user_profile
        )
        result = self.create_channel_via_post(
            user_profile,
            name="testchannel",
            extra_post_data=dict(
                description="test channel",
                can_administer_channel_group=orjson.dumps(
                    {
                        "direct_members": [cordelia.id],
                        "direct_subgroups": [nobody_group.id],
                    }
                ).decode(),
                folder_id=orjson.dumps(channel_folder.id).decode(),
            ),
        )
        self.assert_json_success(result)
        stream = get_stream("testchannel", user_profile.realm)
        self.assertEqual(stream.name, "testchannel")
        self.assertEqual(stream.description, "test channel")

        # Confirm channel created notification message in channel events topic.
        message = self.get_last_message()
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.recipient.type_id, stream.id)
        self.assertEqual(message.topic_name(), Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME)
        self.assertEqual(message.sender_id, self.notification_bot(user_profile.realm).id)
        expected_message_content = (
            f"**Public** channel created by @_**{user_profile.full_name}|{user_profile.id}**. **Description:**\n"
            "```` quote\ntest channel\n````"
        )
        self.assertEqual(message.content, expected_message_content)

        # Test channel created notification is not sent if `send_channel_events_messages`
        # realm setting is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        result = self.create_channel_via_post(
            user_profile,
            name="testchannel2",
        )
        self.assert_json_success(result)
        stream = get_stream("testchannel2", user_profile.realm)
        self.assertEqual(stream.name, "testchannel2")
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

        # Creating an existing channel should return an error.
        result = self.create_channel_via_post(user_profile, name="basketball")
        self.assert_json_error(result, "Channel 'basketball' already exists", status_code=409)

        # Test creating channel with no subscribers
        post_data = {
            "name": "no-sub-channel",
            "subscribers": orjson.dumps([]).decode(),
        }

        result = self.api_post(
            user_profile,
            "/api/v1/channels/create",
            post_data,
        )
        self.assert_json_success(result)
        stream = get_stream("no-sub-channel", user_profile.realm)
        self.assertEqual(stream.name, "no-sub-channel")
        self.assertEqual(stream.subscriber_count, 0)

        # Test creating channel with invalid user ID.
        result = self.create_channel_via_post(
            user_profile,
            name="invalid-user-channel",
            subscribers=[12, 1000],
        )
        self.assert_json_error(result, "No such user")

    def test_channel_creation_miscellaneous(self) -> None:
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        cordelia = self.example_user("cordelia")

        result = self.create_channel_via_post(
            iago, extra_post_data={"message_retention_days": orjson.dumps(10).decode()}
        )
        self.assert_json_error(result, "Must be an organization owner")

        result = self.create_channel_via_post(
            desdemona,
            [iago.id],
            name="new_channel",
            extra_post_data={"message_retention_days": orjson.dumps(10).decode()},
        )
        self.assert_json_success(result)
        stream = get_stream("new_channel", desdemona.realm)
        self.assertEqual(stream.name, "new_channel")
        self.assertEqual(stream.message_retention_days, 10)

        # Default streams can only be created by admins
        result = self.create_channel_via_post(
            iago,
            name="testing_channel1",
            extra_post_data={"is_default_stream": orjson.dumps(True).decode()},
            invite_only=True,
        )
        self.assert_json_error(result, "A default channel cannot be private.")

        result = self.create_channel_via_post(
            iago,
            name="testing_channel1",
            extra_post_data={"is_default_stream": orjson.dumps(True).decode()},
            invite_only=False,
        )
        self.assert_json_success(result)
        stream = get_stream("testing_channel1", iago.realm)
        self.assertEqual(stream.name, "testing_channel1")
        self.assertTrue(stream.id in get_default_stream_ids_for_realm(iago.realm.id))

        # Only org owners can create web public streams by default, if they are enabled.
        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            self.assertFalse(desdemona.realm.has_web_public_streams())
            result = self.create_channel_via_post(
                desdemona,
                name="testing_web_public_channel",
                is_web_public=True,
            )
            self.assert_json_error(result, "Web-public channels are not enabled.")

        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=True):
            self.assertTrue(desdemona.realm.has_web_public_streams())
            result = self.create_channel_via_post(
                desdemona,
                name="testing_web_public_channel",
                is_web_public=True,
            )
            self.assert_json_success(result)
            stream = get_stream("testing_web_public_channel", desdemona.realm)
            self.assertEqual(stream.name, "testing_web_public_channel")

        polonius = self.example_user("polonius")
        result = self.create_channel_via_post(
            polonius,
            name="testing_channel4",
            invite_only=True,
        )
        self.assert_json_error(result, "Not allowed for guest users")

        # topics policy
        owners = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm_for_sharding=cordelia.realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            cordelia.realm, "can_set_topics_policy_group", owners, acting_user=None
        )
        self.assertTrue(desdemona.can_set_topics_policy())
        self.assertFalse(cordelia.can_set_topics_policy())
        result = self.create_channel_via_post(
            cordelia,
            name="testing_channel4",
            extra_post_data={
                "topics_policy": orjson.dumps(
                    StreamTopicsPolicyEnum.disable_empty_topic.name
                ).decode()
            },
        )
        self.assert_json_error(result, "Insufficient permission")

        result = self.create_channel_via_post(
            desdemona,
            name="testing_channel4",
            extra_post_data={
                "topics_policy": orjson.dumps(
                    StreamTopicsPolicyEnum.disable_empty_topic.name
                ).decode()
            },
        )
        self.assert_json_success(result)
        stream = get_stream("testing_channel4", desdemona.realm)
        self.assertEqual(stream.name, "testing_channel4")
        self.assertEqual(stream.topics_policy, StreamTopicsPolicyEnum.disable_empty_topic.value)

    def _test_group_based_settings_for_creating_channels(
        self,
        stream_policy: str,
        *,
        invite_only: bool,
        is_web_public: bool,
    ) -> None:
        def check_permission_to_create_channel(
            user: UserProfile, stream_name: str, *, expect_fail: bool = False
        ) -> None:
            result = self.create_channel_via_post(
                user,
                name=stream_name,
                invite_only=invite_only,
                is_web_public=is_web_public,
            )
            if expect_fail:
                self.assert_json_error(result, "Insufficient permission")
                return

            self.assert_json_success(result)
            self.assertTrue(
                Stream.objects.filter(name=stream_name, realm_id=user.realm.id).exists()
            )

        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")

        # System groups case
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=cordelia.realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            cordelia.realm, stream_policy, nobody_group, acting_user=None
        )

        check_permission_to_create_channel(
            cordelia,
            "testing_channel_group_permission1",
            expect_fail=True,
        )

        check_permission_to_create_channel(
            iago, "testing_channel_group_permission1", expect_fail=True
        )

        member_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=cordelia.realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            cordelia.realm, stream_policy, member_group, acting_user=None
        )
        check_permission_to_create_channel(
            cordelia,
            "testing_channel_group_permission1",
        )

        check_permission_to_create_channel(iago, "testing_channel_group_permission2")

        admin_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS,
            realm_for_sharding=cordelia.realm,
            is_system_group=True,
        )
        do_change_realm_permission_group_setting(
            cordelia.realm, stream_policy, admin_group, acting_user=None
        )
        check_permission_to_create_channel(
            cordelia,
            "testing_channel_group_permission3",
            expect_fail=True,
        )
        check_permission_to_create_channel(iago, "testing_channel_group_permission3")

        # User defined group case
        leadership_group = check_add_user_group(
            cordelia.realm, "Leadership", [desdemona], acting_user=desdemona
        )
        do_change_realm_permission_group_setting(
            cordelia.realm, stream_policy, leadership_group, acting_user=None
        )
        check_permission_to_create_channel(
            cordelia,
            "testing_channel_group_permission4",
            expect_fail=True,
        )
        check_permission_to_create_channel(
            desdemona,
            "testing_channel_group_permission4",
        )

        # Anonymous group case
        staff_group = check_add_user_group(cordelia.realm, "Staff", [iago], acting_user=iago)
        setting_group = self.create_or_update_anonymous_group_for_setting([cordelia], [staff_group])
        do_change_realm_permission_group_setting(
            cordelia.realm, stream_policy, setting_group, acting_user=None
        )
        check_permission_to_create_channel(
            desdemona,
            "testing_channel_group_permission5",
            expect_fail=True,
        )
        check_permission_to_create_channel(iago, "testing_channel_group_permission5")
        check_permission_to_create_channel(
            cordelia,
            "testing_channel_group_permission6",
        )

    def test_group_based_permissions_for_creating_private_streams(self) -> None:
        self._test_group_based_settings_for_creating_channels(
            "can_create_private_channel_group",
            invite_only=True,
            is_web_public=False,
        )

    def test_group_based_permissions_for_creating_public_streams(self) -> None:
        self._test_group_based_settings_for_creating_channels(
            "can_create_public_channel_group",
            invite_only=False,
            is_web_public=False,
        )

    def test_group_based_permissions_for_creating_web_public_streams(self) -> None:
        self._test_group_based_settings_for_creating_channels(
            "can_create_web_public_channel_group",
            invite_only=False,
            is_web_public=True,
        )

    def test_auto_mark_stream_created_message_as_read_for_stream_creator(self) -> None:
        # This test relies on email == delivery_email for
        # convenience.
        reset_email_visibility_to_everyone_in_zulip_realm()

        realm = Realm.objects.get(name="Zulip Dev")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")

        # Establish a stream for notifications.
        announce_stream = ensure_stream(
            realm, "announce", False, "announcements here.", acting_user=None
        )
        realm.new_stream_announcements_stream_id = announce_stream.id
        realm.save(update_fields=["new_stream_announcements_stream_id"])

        self.subscribe(iago, announce_stream.name)
        self.subscribe(hamlet, announce_stream.name)

        self.login_user(iago)

        initial_message_count = Message.objects.count()
        initial_usermessage_count = UserMessage.objects.count()

        data = {
            "subscriptions": '[{"name":"brand new stream","description":""}]',
            "history_public_to_subscribers": "true",
            "invite_only": "false",
            "announce": "true",
            "principals": orjson.dumps([iago.id, aaron.id, cordelia.id, hamlet.id]).decode(),
        }

        response = self.client_post("/json/users/me/subscriptions", data)

        final_message_count = Message.objects.count()
        final_usermessage_count = UserMessage.objects.count()

        expected_response = {
            "result": "success",
            "msg": "",
            "subscribed": {
                "10": ["brand new stream"],
                "11": ["brand new stream"],
                "6": ["brand new stream"],
                "8": ["brand new stream"],
            },
            "already_subscribed": {},
            "new_subscription_messages_sent": True,
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(orjson.loads(response.content), expected_response)

        # 2 messages should be created, one in announce and one in the new stream itself.
        self.assertEqual(final_message_count - initial_message_count, 2)
        # 4 UserMessages per subscriber: One for each of the subscribers, plus 1 for
        # each user in the notifications stream.
        announce_stream_subs = Subscription.objects.filter(recipient=announce_stream.recipient)
        self.assertEqual(
            final_usermessage_count - initial_usermessage_count, 4 + announce_stream_subs.count()
        )

        def get_unread_stream_data(user: UserProfile) -> list[UnreadStreamInfo]:
            raw_unread_data = get_raw_unread_data(user)
            aggregated_data = aggregate_unread_data(raw_unread_data, allow_empty_topic_name=True)
            return aggregated_data["streams"]

        stream_id = Stream.objects.get(name="brand new stream").id
        iago_unread_messages = get_unread_stream_data(iago)
        hamlet_unread_messages = get_unread_stream_data(hamlet)

        # The stream creation messages should be unread for Hamlet
        self.assert_length(hamlet_unread_messages, 2)

        # According to the code in zerver/views/streams/add_subscriptions_backend
        # the notification stream message is sent first, then the new stream's message.
        self.assertEqual(hamlet_unread_messages[1]["stream_id"], stream_id)

        # But it should be marked as read for Iago, the stream creator.
        self.assert_length(iago_unread_messages, 0)

    def test_can_administer_channel_group_default_on_stream_creation(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        nobody_system_group = NamedUserGroup.objects.get(
            name="role:nobody", realm_for_sharding=realm, is_system_group=True
        )

        stream, _created = create_stream_if_needed(
            realm, "new stream without acting user", invite_only=True
        )
        self.assertEqual(stream.can_administer_channel_group.id, nobody_system_group.id)

        stream, _created = create_stream_if_needed(
            realm, "new stream with acting user", acting_user=user
        )
        self.assertCountEqual(stream.can_administer_channel_group.direct_members.all(), [user])

    def test_can_create_topic_group_for_protected_history_streams(self) -> None:
        """
        For channels with protected history, can_create_topic_group can only
        be set to "role:everyone" system group.
        """
        user = self.example_user("iago")
        realm = user.realm
        self.login_user(user)

        everyone_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)

        error_msg = "Unsupported parameter combination: history_public_to_subscribers, can_create_topic_group"

        def check_create_protected_history_stream(
            can_create_topic_group: int | UserGroupMembersData,
            expect_fail: bool = False,
        ) -> None:
            stream_name = "test_protected_history_stream"
            subscriptions = [{"name": stream_name}]
            extra_post_data = {
                "history_public_to_subscribers": orjson.dumps(False).decode(),
                "can_create_topic_group": orjson.dumps(can_create_topic_group).decode(),
            }

            result = self.subscribe_via_post(
                user,
                subscriptions,
                extra_post_data,
                invite_only=True,
                subdomain="zulip",
                allow_fail=expect_fail,
            )

            if expect_fail:
                self.assert_json_error(result, error_msg)
            else:
                self.assert_json_success(result)
                stream = get_stream(stream_name, realm)
                self.assertFalse(stream.history_public_to_subscribers)
                self.assertEqual(stream.can_create_topic_group_id, everyone_system_group.id)
                # Delete the created stream so that we can create stream
                # with same name for further cases.
                stream.delete()

            # Test creating channel using "/channels/create" endpoint as well.
            result = self.create_channel_via_post(
                user,
                name=stream_name,
                extra_post_data=extra_post_data,
                invite_only=True,
            )

            if expect_fail:
                self.assert_json_error(result, error_msg)
                return

            self.assert_json_success(result)
            stream = get_stream(stream_name, realm)
            self.assertFalse(stream.history_public_to_subscribers)
            self.assertEqual(stream.can_create_topic_group_id, everyone_system_group.id)
            # Delete the created stream so that we can create stream
            # with same name for further cases.
            stream.delete()

        # Testing for everyone group.
        check_create_protected_history_stream(everyone_system_group.id)

        # Testing for a system group.
        check_create_protected_history_stream(moderators_system_group.id, expect_fail=True)

        # Testing for a user defined group.
        check_create_protected_history_stream(hamletcharacters_group.id, expect_fail=True)

        # Testing for an anonymous group.
        check_create_protected_history_stream(
            UserGroupMembersData(
                direct_members=[user.id], direct_subgroups=[moderators_system_group.id]
            ),
            expect_fail=True,
        )

        # Testing for an anonymous group without members and
        # only everyone group as subgroup.
        check_create_protected_history_stream(
            UserGroupMembersData(direct_members=[], direct_subgroups=[everyone_system_group.id]),
        )

    def do_test_permission_setting_on_stream_creation(self, setting_name: str) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        moderators_system_group = NamedUserGroup.objects.get(
            name="role:moderators", realm_for_sharding=realm, is_system_group=True
        )

        permission_config = Stream.stream_permission_group_settings[setting_name]

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        extra_post_data = {}
        extra_post_data[setting_name] = orjson.dumps(moderators_system_group.id).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            subdomain="zulip",
        )
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(getattr(stream, setting_name).id, moderators_system_group.id)
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        result = self.subscribe_via_post(user, subscriptions, subdomain="zulip")
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        if permission_config.default_group_name == "channel_creator":
            self.assertEqual(list(getattr(stream, setting_name).direct_members.all()), [user])
            self.assertEqual(
                list(getattr(stream, setting_name).direct_subgroups.all()),
                [],
            )
        else:
            default_group = NamedUserGroup.objects.get(
                name=permission_config.default_group_name,
                realm_for_sharding=realm,
                is_system_group=True,
            )
            self.assertEqual(getattr(stream, setting_name).id, default_group.id)
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        hamletcharacters_group = NamedUserGroup.objects.get(
            name="hamletcharacters", realm_for_sharding=realm
        )
        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        extra_post_data[setting_name] = orjson.dumps(hamletcharacters_group.id).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(getattr(stream, setting_name).id, hamletcharacters_group.id)
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        extra_post_data[setting_name] = orjson.dumps(
            {"direct_members": [user.id], "direct_subgroups": [moderators_system_group.id]}
        ).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(list(getattr(stream, setting_name).direct_members.all()), [user])
        self.assertEqual(
            list(getattr(stream, setting_name).direct_subgroups.all()),
            [moderators_system_group],
        )
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm_for_sharding=realm
        )

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        extra_post_data[setting_name] = orjson.dumps(
            {"direct_members": [], "direct_subgroups": []}
        ).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(getattr(stream, setting_name).id, nobody_group.id)
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        owners_group = NamedUserGroup.objects.get(
            name="role:owners", is_system_group=True, realm_for_sharding=realm
        )
        extra_post_data[setting_name] = orjson.dumps(owners_group.id).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(getattr(stream, setting_name).id, owners_group.id)
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        extra_post_data[setting_name] = orjson.dumps(nobody_group.id).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(getattr(stream, setting_name).id, nobody_group.id)
        # Delete the created stream, so we can create a new one for
        # testing another setting value.
        stream.delete()

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        everyone_group = NamedUserGroup.objects.get(
            name="role:everyone", is_system_group=True, realm_for_sharding=realm
        )
        extra_post_data[setting_name] = orjson.dumps(everyone_group.id).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        if permission_config.allow_everyone_group:
            self.assert_json_success(result)
            stream = get_stream("new_stream", realm)
            self.assertEqual(getattr(stream, setting_name).id, everyone_group.id)
            # Delete the created stream, so we can create a new one for
            # testing another setting value.
            stream.delete()
        else:
            self.assert_json_error(
                result,
                f"'{setting_name}' setting cannot be set to 'role:everyone' group.",
            )

        subscriptions = [{"name": "new_stream", "description": "New stream"}]
        internet_group = NamedUserGroup.objects.get(
            name="role:internet", is_system_group=True, realm_for_sharding=realm
        )
        extra_post_data[setting_name] = orjson.dumps(internet_group.id).decode()
        result = self.subscribe_via_post(
            user,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_error(
            result,
            f"'{setting_name}' setting cannot be set to 'role:internet' group.",
        )

    def test_permission_settings_on_stream_creation(self) -> None:
        realm = get_realm("zulip")
        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_set_delete_message_policy_group",
            members_system_group,
            acting_user=None,
        )

        for setting_name in Stream.stream_permission_group_settings:
            self.do_test_permission_setting_on_stream_creation(setting_name)

    def test_default_permission_settings_on_stream_creation(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm
        subscriptions = [{"name": "new_stream", "description": "New stream"}]

        self.login("hamlet")
        with self.capture_send_event_calls(expected_num_events=4) as events:
            result = self.subscribe_via_post(
                hamlet,
                subscriptions,
            )
        self.assert_json_success(result)

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm_for_sharding=realm, is_system_group=True
        )

        stream = get_stream("new_stream", realm)
        self.assertEqual(
            list(
                stream.can_administer_channel_group.direct_members.all().values_list(
                    "id", flat=True
                )
            ),
            [hamlet.id],
        )
        self.assertEqual(
            list(
                stream.can_administer_channel_group.direct_subgroups.all().values_list(
                    "id", flat=True
                )
            ),
            [],
        )

        self.assertEqual(stream.can_add_subscribers_group_id, nobody_group.id)
        self.assertEqual(stream.can_remove_subscribers_group_id, admins_group.id)
        self.assertEqual(stream.can_send_message_group_id, everyone_group.id)
        self.assertEqual(stream.can_subscribe_group_id, nobody_group.id)

        # Check setting values sent in stream creation events.
        event_stream = events[0]["event"]["streams"][0]
        self.assertEqual(
            event_stream["can_administer_channel_group"],
            UserGroupMembersDict(direct_members=[hamlet.id], direct_subgroups=[]),
        )

        self.assertEqual(event_stream["can_add_subscribers_group"], nobody_group.id)
        self.assertEqual(event_stream["can_remove_subscribers_group"], admins_group.id)
        self.assertEqual(event_stream["can_send_message_group"], everyone_group.id)
        self.assertEqual(event_stream["can_subscribe_group"], nobody_group.id)

    def test_acting_user_is_creator(self) -> None:
        """
        If backend calls provide an acting_user while trying to
        create streams, assign acting_user as the stream creator
        """
        hamlet = self.example_user("hamlet")
        new_streams, _ = create_streams_if_needed(
            hamlet.realm,
            [
                StreamDict(
                    name="hamlet's test stream",
                    description="No description",
                    invite_only=True,
                    is_web_public=True,
                )
            ],
            acting_user=hamlet,
        )
        created_stream = new_streams[0]
        self.assertEqual(created_stream.creator_id, hamlet.id)

    def test_channel_create_message_exists_for_all_policy_types(self) -> None:
        """
        Create a channel for each policy type to ensure they all have a "new channel" message.
        """
        # this is to check if the appropriate channel name is present in the "new channel" message
        policy_key_map: dict[str, str] = {
            "web_public": "**Web-public**",
            "public": "**Public**",
            "private_shared_history": "**Private, shared history**",
            "private_protected_history": "**Private, protected history**",
        }
        for policy_key, policy_dict in Stream.PERMISSION_POLICIES.items():
            channel_creator = self.example_user("desdemona")
            subdomain = "zulip"

            new_channel_name = f"New {policy_key} channel"
            result = self.api_post(
                channel_creator,
                "/api/v1/users/me/subscriptions",
                {
                    "subscriptions": orjson.dumps([{"name": new_channel_name}]).decode(),
                    "is_web_public": orjson.dumps(policy_dict["is_web_public"]).decode(),
                    "invite_only": orjson.dumps(policy_dict["invite_only"]).decode(),
                    "history_public_to_subscribers": orjson.dumps(
                        policy_dict["history_public_to_subscribers"]
                    ).decode(),
                },
                subdomain=subdomain,
            )
            self.assert_json_success(result)
            new_channel = get_stream(new_channel_name, channel_creator.realm)
            channel_events_messages = get_topic_messages(
                channel_creator, new_channel, "channel events"
            )

            self.assert_length(channel_events_messages, 1)
            self.assertIn(policy_key_map[policy_key], channel_events_messages[0].content)

    def test_adding_channels_to_folder_during_creation(self) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        channel_folder = check_add_channel_folder(realm, "Backend", "", acting_user=iago)

        subscriptions = [
            {"name": "new_stream", "description": "New stream"},
            {"name": "new_stream_2", "description": "New stream 2"},
        ]
        extra_post_data = {}

        extra_post_data["folder_id"] = orjson.dumps(99).decode()
        result = self.subscribe_via_post(
            hamlet,
            subscriptions,
            extra_post_data,
            allow_fail=True,
            subdomain="zulip",
        )
        self.assert_json_error(result, "Invalid channel folder ID")

        extra_post_data["folder_id"] = orjson.dumps(channel_folder.id).decode()
        result = self.subscribe_via_post(
            hamlet,
            subscriptions,
            extra_post_data,
            subdomain="zulip",
        )
        stream = get_stream("new_stream", realm)
        self.assertEqual(stream.folder, channel_folder)
        stream = get_stream("new_stream_2", realm)
        self.assertEqual(stream.folder, channel_folder)

        subscriptions = [
            {"name": "new_stream_3", "description": "New stream 3"},
            {"name": "new_stream_4", "description": "New stream 4"},
        ]
        extra_post_data = {}
        result = self.subscribe_via_post(
            hamlet,
            subscriptions,
            extra_post_data,
            subdomain="zulip",
        )
        stream = get_stream("new_stream_3", realm)
        self.assertIsNone(stream.folder)
        stream = get_stream("new_stream_4", realm)
        self.assertIsNone(stream.folder)

    def test_stream_message_retention_days_on_stream_creation(self) -> None:
        """
        Only admins can create streams with message_retention_days
        with value other than None.
        """
        admin = self.example_user("iago")

        streams_raw: list[StreamDict] = [
            {
                "name": "new_stream",
                "message_retention_days": 10,
                "is_web_public": False,
            }
        ]

        request_settings_dict = dict.fromkeys(Stream.stream_permission_group_settings)

        with self.assertRaisesRegex(JsonableError, "Must be an organization owner"):
            list_to_streams(
                streams_raw, admin, autocreate=True, request_settings_dict=request_settings_dict
            )

        streams_raw = [
            {
                "name": "new_stream",
                "message_retention_days": -1,
                "is_web_public": False,
            }
        ]
        with self.assertRaisesRegex(JsonableError, "Must be an organization owner"):
            list_to_streams(
                streams_raw, admin, autocreate=True, request_settings_dict=request_settings_dict
            )

        streams_raw = [
            {
                "name": "new_stream",
                "message_retention_days": None,
                "is_web_public": False,
            }
        ]
        result = list_to_streams(
            streams_raw, admin, autocreate=True, request_settings_dict=request_settings_dict
        )
        self.assert_length(result[0], 0)
        self.assert_length(result[1], 1)
        self.assertEqual(result[1][0].name, "new_stream")
        self.assertEqual(result[1][0].message_retention_days, None)

        owner = self.example_user("desdemona")
        realm = owner.realm
        streams_raw = [
            {
                "name": "new_stream1",
                "message_retention_days": 10,
                "is_web_public": False,
            },
            {
                "name": "new_stream2",
                "message_retention_days": -1,
                "is_web_public": False,
            },
            {
                "name": "new_stream3",
                "is_web_public": False,
            },
        ]

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=admin)
        with self.assertRaisesRegex(
            JsonableError, "Available on Zulip Cloud Standard. Upgrade to access."
        ):
            list_to_streams(
                streams_raw, owner, autocreate=True, request_settings_dict=request_settings_dict
            )

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_SELF_HOSTED, acting_user=admin)
        result = list_to_streams(
            streams_raw, owner, autocreate=True, request_settings_dict=request_settings_dict
        )
        self.assert_length(result[0], 0)
        self.assert_length(result[1], 3)
        self.assertEqual(result[1][0].name, "new_stream1")
        self.assertEqual(result[1][0].message_retention_days, 10)
        self.assertEqual(result[1][1].name, "new_stream2")
        self.assertEqual(result[1][1].message_retention_days, -1)
        self.assertEqual(result[1][2].name, "new_stream3")
        self.assertEqual(result[1][2].message_retention_days, None)

    def test_permission_settings_when_creating_multiple_streams(self) -> None:
        """
        Check that different anonymous group is used for each setting when creating
        multiple streams in a single request.
        """
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )

        subscriptions = [
            {"name": "new_stream", "description": "New stream"},
            {"name": "new_stream_2", "description": "New stream 2"},
        ]
        extra_post_data = {
            "can_add_subscribers_group": orjson.dumps(
                {
                    "direct_members": [cordelia.id],
                    "direct_subgroups": [moderators_group.id],
                }
            ).decode(),
        }

        result = self.subscribe_via_post(
            hamlet,
            subscriptions,
            extra_post_data,
        )
        self.assert_json_success(result)

        stream_1 = get_stream("new_stream", realm)
        stream_2 = get_stream("new_stream_2", realm)

        # Check value of can_administer_channel_group setting which is set to its default
        # of an anonymous group with creator as the only member.
        self.assertFalse(hasattr(stream_1.can_administer_channel_group, "named_user_group"))
        self.assertFalse(hasattr(stream_2.can_administer_channel_group, "named_user_group"))
        self.assertEqual(list(stream_1.can_administer_channel_group.direct_members.all()), [hamlet])
        self.assertEqual(list(stream_2.can_administer_channel_group.direct_members.all()), [hamlet])
        self.assertEqual(list(stream_1.can_administer_channel_group.direct_subgroups.all()), [])
        self.assertEqual(list(stream_2.can_administer_channel_group.direct_subgroups.all()), [])

        # Check value of can_add_subscribers_group setting which is set to an anonymous
        # group as request.
        self.assertFalse(hasattr(stream_1.can_add_subscribers_group, "named_user_group"))
        self.assertFalse(hasattr(stream_2.can_add_subscribers_group, "named_user_group"))
        self.assertEqual(list(stream_1.can_add_subscribers_group.direct_members.all()), [cordelia])
        self.assertEqual(list(stream_2.can_add_subscribers_group.direct_members.all()), [cordelia])
        self.assertEqual(
            list(stream_1.can_add_subscribers_group.direct_subgroups.all()), [moderators_group]
        )
        self.assertEqual(
            list(stream_2.can_add_subscribers_group.direct_subgroups.all()), [moderators_group]
        )

        # Check that for each stream, different anonymous group is used.
        self.assertNotEqual(
            stream_1.can_administer_channel_group_id, stream_2.can_administer_channel_group_id
        )
        self.assertNotEqual(
            stream_1.can_add_subscribers_group_id, stream_2.can_add_subscribers_group_id
        )
