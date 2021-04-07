from datetime import datetime, timezone
from unittest import mock

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_mutes import add_user_mute, get_user_mutes, user_is_muted


class MutedUsersTests(ZulipTestCase):
    # Hamlet does the muting/unmuting, and Cordelia gets muted/unmuted.
    def test_get_user_mutes(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        muted_users = get_user_mutes(hamlet)
        self.assertEqual(muted_users, [])
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with mock.patch("zerver.lib.user_mutes.timezone_now", return_value=mute_time):
            add_user_mute(user_profile=hamlet, muted_user=cordelia)

        muted_users = get_user_mutes(hamlet)
        self.assertEqual(len(muted_users), 1)

        self.assertDictEqual(
            muted_users[0],
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
        )

    def test_add_muted_user_mute_self(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        url = "/api/v1/users/me/muted_users/{}".format(hamlet.id)
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "Cannot mute self")

    def test_add_muted_user_mute_bot(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
            "bot_type": "1",
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        muted_id = result.json()["user_id"]

        url = "/api/v1/users/me/muted_users/{}".format(muted_id)
        result = self.api_post(hamlet, url)
        # Currently we do not allow muting bots. This is the error message
        # from `access_user_by_id`.
        self.assert_json_error(result, "No such user")

    def test_add_muted_user_mute_twice(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        add_user_mute(
            user_profile=hamlet,
            muted_user=cordelia,
        )

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "User already muted")

    def test_add_muted_user_valid_data(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with mock.patch("zerver.views.muting.timezone_now", return_value=mute_time):
            url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        self.assertIn(
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
            get_user_mutes(hamlet),
        )
        self.assertTrue(user_is_muted(hamlet, cordelia))

    def test_remove_muted_user_unmute_before_muting(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_delete(hamlet, url)
        self.assert_json_error(result, "User is not muted")

    def test_remove_muted_user_valid_data(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        add_user_mute(user_profile=hamlet, muted_user=cordelia, date_muted=mute_time)

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_delete(hamlet, url)

        self.assert_json_success(result)
        self.assertNotIn(
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
            get_user_mutes(hamlet),
        )
        self.assertFalse(user_is_muted(hamlet, cordelia))
