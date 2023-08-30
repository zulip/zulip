import os
from datetime import timedelta
from typing import Any
from unittest import mock

import dateutil.parser
import orjson

from zerver.data_import.gitter import do_convert_data, get_usermentions
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, UserProfile, get_realm
from zproject.backends import (
    AUTH_BACKEND_NAME_MAP,
    GitHubAuthBackend,
    auth_enabled_helper,
    github_auth_enabled,
)


class GitterImporter(ZulipTestCase):
    @mock.patch("zerver.data_import.gitter.process_avatars", return_value=[])
    def test_gitter_import_data_conversion(self, mock_process_avatars: mock.Mock) -> None:
        output_dir = self.make_import_output_dir("gitter")
        gitter_file = os.path.join(os.path.dirname(__file__), "fixtures/gitter_data.json")

        # We need some time-mocking to set up user soft-deactivation logic.
        # One of the messages in the import data
        # is significantly older than the other one. We mock the current time in the relevant module
        # to match the sent time of the more recent message - to make it look like one of the messages
        # is very recent, while the other one is old. This should cause that the sender of the recent
        # message to NOT be soft-deactivated, while the sender of the other one is.
        with open(gitter_file) as f:
            gitter_data = orjson.loads(f.read())
        sent_datetime = dateutil.parser.parse(gitter_data[1]["sent"])
        with self.assertLogs(level="INFO"), mock.patch(
            "zerver.data_import.import_util.timezone_now",
            return_value=sent_datetime + timedelta(days=1),
        ):
            do_convert_data(gitter_file, output_dir)

        def read_file(output_file: str) -> Any:
            full_path = os.path.join(output_dir, output_file)
            with open(full_path, "rb") as f:
                return orjson.loads(f.read())

        self.assertEqual(os.path.exists(os.path.join(output_dir, "avatars")), True)
        self.assertEqual(os.path.exists(os.path.join(output_dir, "emoji")), True)
        self.assertEqual(os.path.exists(os.path.join(output_dir, "attachment.json")), True)

        realm = read_file("realm.json")

        # test realm
        self.assertEqual(
            "Organization imported from Gitter!", realm["zerver_realm"][0]["description"]
        )

        # test users
        exported_user_ids = self.get_set(realm["zerver_userprofile"], "id")
        exported_user_full_name = self.get_set(realm["zerver_userprofile"], "full_name")
        self.assertIn("User Full Name", exported_user_full_name)
        exported_user_email = self.get_set(realm["zerver_userprofile"], "email")
        self.assertIn("username2@users.noreply.github.com", exported_user_email)

        # test stream
        self.assert_length(realm["zerver_stream"], 1)
        self.assertEqual(realm["zerver_stream"][0]["name"], "from gitter")
        self.assertEqual(realm["zerver_stream"][0]["deactivated"], False)
        self.assertEqual(realm["zerver_stream"][0]["realm"], realm["zerver_realm"][0]["id"])

        self.assertEqual(
            realm["zerver_defaultstream"][0]["stream"], realm["zerver_stream"][0]["id"]
        )

        # test recipient
        exported_recipient_id = self.get_set(realm["zerver_recipient"], "id")
        exported_recipient_type = self.get_set(realm["zerver_recipient"], "type")
        self.assertEqual({1, 2}, exported_recipient_type)

        # test subscription
        exported_subscription_userprofile = self.get_set(
            realm["zerver_subscription"], "user_profile"
        )
        self.assertEqual({0, 1}, exported_subscription_userprofile)
        exported_subscription_recipient = self.get_set(realm["zerver_subscription"], "recipient")
        self.assert_length(exported_subscription_recipient, 3)
        self.assertIn(realm["zerver_subscription"][1]["recipient"], exported_recipient_id)

        messages = read_file("messages-000001.json")

        # test messages
        exported_messages_id = self.get_set(messages["zerver_message"], "id")
        self.assertIn(messages["zerver_message"][0]["sender"], exported_user_ids)
        self.assertIn(messages["zerver_message"][1]["recipient"], exported_recipient_id)
        self.assertIn(messages["zerver_message"][0]["content"], "test message")

        # test usermessages and soft-deactivation of users
        [user_should_be_long_term_idle] = (
            user
            for user in realm["zerver_userprofile"]
            if user["delivery_email"] == "username1@users.noreply.github.com"
        )
        [user_should_not_be_long_term_idle] = (
            user
            for user in realm["zerver_userprofile"]
            if user["delivery_email"] == "username2@users.noreply.github.com"
        )
        self.assertEqual(user_should_be_long_term_idle["long_term_idle"], True)

        # Only the user who's not soft-deactivated gets UserMessages.
        exported_usermessage_userprofile = self.get_set(
            messages["zerver_usermessage"], "user_profile"
        )
        self.assertEqual(
            {user_should_not_be_long_term_idle["id"]}, exported_usermessage_userprofile
        )
        exported_usermessage_message = self.get_set(messages["zerver_usermessage"], "message")
        self.assertEqual(exported_usermessage_message, exported_messages_id)

    @mock.patch("zerver.data_import.gitter.process_avatars", return_value=[])
    def test_gitter_import_to_existing_database(self, mock_process_avatars: mock.Mock) -> None:
        output_dir = self.make_import_output_dir("gitter")
        gitter_file = os.path.join(os.path.dirname(__file__), "fixtures/gitter_data.json")
        with self.assertLogs(level="INFO"):
            do_convert_data(gitter_file, output_dir)

        with self.assertLogs(level="INFO"):
            do_import_realm(output_dir, "test-gitter-import")

        realm = get_realm("test-gitter-import")

        # test rendered_messages
        realm_users = UserProfile.objects.filter(realm=realm)
        messages = Message.objects.filter(realm_id=realm.id, sender__in=realm_users)
        for message in messages:
            self.assertIsNotNone(message.rendered_content, None)

        self.assertTrue(github_auth_enabled(realm))
        for auth_backend_name in AUTH_BACKEND_NAME_MAP:
            if auth_backend_name == GitHubAuthBackend.auth_backend_name:
                continue

            self.assertFalse(auth_enabled_helper([auth_backend_name], realm))

    def test_get_usermentions(self) -> None:
        user_map = {"57124a4": 3, "57124b4": 5, "57124c4": 8}
        user_short_name_to_full_name = {
            "user": "user name",
            "user2": "user2",
            "user3": "user name 3",
            "user4": "user 4",
        }
        messages = [
            {"text": "hi @user", "mentions": [{"screenName": "user", "userId": "57124a4"}]},
            {
                "text": "hi @user2 @user3",
                "mentions": [
                    {"screenName": "user2", "userId": "57124b4"},
                    {"screenName": "user3", "userId": "57124c4"},
                ],
            },
            {"text": "hi @user4", "mentions": [{"screenName": "user4"}]},
            {"text": "hi @user5", "mentions": [{"screenName": "user", "userId": "5712ds4"}]},
        ]

        self.assertEqual(get_usermentions(messages[0], user_map, user_short_name_to_full_name), [3])
        self.assertEqual(messages[0]["text"], "hi @**user name**")
        self.assertEqual(
            get_usermentions(messages[1], user_map, user_short_name_to_full_name), [5, 8]
        )
        self.assertEqual(messages[1]["text"], "hi @**user2** @**user name 3**")
        self.assertEqual(get_usermentions(messages[2], user_map, user_short_name_to_full_name), [])
        self.assertEqual(messages[2]["text"], "hi @user4")
        self.assertEqual(get_usermentions(messages[3], user_map, user_short_name_to_full_name), [])
        self.assertEqual(messages[3]["text"], "hi @user5")
