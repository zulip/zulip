from datetime import datetime, timezone
from unittest import mock

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_mutes import add_user_mute, get_user_mutes, user_is_muted


class MutedUsersTests(ZulipTestCase):
    def test_get_user_mutes(self) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        muted_users = get_user_mutes(othello)
        self.assertEqual(muted_users, [])
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with mock.patch(
            "zerver.lib.user_mutes.timezone_now",
            return_value=mute_time,
        ):
            add_user_mute(user_profile=othello, muted_user=cordelia)

        muted_users = get_user_mutes(othello)
        self.assertEqual(len(muted_users), 1)

        self.assertDictEqual(
            muted_users[0],
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
        )

    def test_add_muted_user_mute_self(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        url = "/api/v1/users/me/muted_users/{}".format(user.id)
        result = self.api_post(user, url)
        self.assert_json_error(result, "Cannot mute self")

    def test_add_muted_user_mute_bot(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
            "bot_type": "1",
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        muted_id = result.json()["user_id"]

        url = "/api/v1/users/me/muted_users/{}".format(muted_id)
        result = self.api_post(user, url)
        # Currently we do not allow muting bots. This is the error message
        # from `access_user_by_id`.
        self.assert_json_error(result, "No such user")

    def test_add_muted_user_mute_twice(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        muted_user = self.example_user("cordelia")
        muted_id = muted_user.id

        add_user_mute(
            user_profile=user,
            muted_user=muted_user,
        )

        url = "/api/v1/users/me/muted_users/{}".format(muted_id)
        result = self.api_post(user, url)
        self.assert_json_error(result, "User already muted")

    def test_add_muted_user_valid_data(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        muted_user = self.example_user("cordelia")
        muted_id = muted_user.id

        mock_date_muted = datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp()
        with mock.patch(
            "zerver.views.muting.timezone_now",
            return_value=datetime(2021, 1, 1, tzinfo=timezone.utc),
        ):
            url = "/api/v1/users/me/muted_users/{}".format(muted_id)
            result = self.api_post(user, url)
            self.assert_json_success(result)

        self.assertIn({"id": muted_id, "timestamp": mock_date_muted}, get_user_mutes(user))
        self.assertTrue(user_is_muted(user, muted_user))

    def test_remove_muted_user_unmute_before_muting(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        muted_user = self.example_user("cordelia")
        muted_id = muted_user.id

        url = "/api/v1/users/me/muted_users/{}".format(muted_id)
        result = self.api_delete(user, url)
        self.assert_json_error(result, "User is not muted")

    def test_remove_muted_user_valid_data(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        muted_user = self.example_user("cordelia")
        muted_id = muted_user.id

        add_user_mute(
            user_profile=user,
            muted_user=muted_user,
            date_muted=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )

        url = "/api/v1/users/me/muted_users/{}".format(muted_id)
        result = self.api_delete(user, url)

        mock_date_muted = datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp()
        self.assert_json_success(result)
        self.assertNotIn({"id": muted_id, "timestamp": mock_date_muted}, get_user_mutes(user))
        self.assertFalse(user_is_muted(user, muted_user))
