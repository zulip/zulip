import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase

from zerver.models import UserProfile

from zerver.lib.mute_users import (
    add_user_mute,
    get_user_mutes,
    user_is_muted,
)

class MutedUsersTests(ZulipTestCase):
    def test_user_muting_ids(self) -> None:
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        cordelia  = self.example_user('cordelia')

        muted_users = get_user_mutes(othello)
        self.assertEqual(muted_users, [])

        def mute_user(muted_user: UserProfile) -> None:
            add_user_mute(
                user_profile=othello,
                muted_user_profile=muted_user,
            )

        mute_user(hamlet)
        muted_users = get_user_mutes(othello)
        self.assertEqual(muted_users, [{'id': hamlet.id, 'name': hamlet.full_name}])

        mute_user(cordelia)
        muted_users = get_user_mutes(othello)
        self.assertEqual(muted_users, [{'id': hamlet.id, 'name': hamlet.full_name}, {'id': cordelia.id, 'name': cordelia.full_name}])

    def test_add_muted_user(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        muted_user = self.example_user('cordelia')
        muted_id = muted_user.id
        self.login(email)

        url = '/api/v1/users/me/user_mute/' + str(muted_id)
        data = {'muted_user_profile_id': muted_id}
        result = self.api_put(email, url, data)
        self.assert_json_success(result)

        self.assertIn({'id': muted_id, 'name': muted_user.full_name}, get_user_mutes(user))

        self.assertTrue(user_is_muted(user, muted_user))

    def test_remove_muted_user(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        muted_user = self.example_user('cordelia')
        muted_id = muted_user.id
        self.login(email)

        add_user_mute(
            user_profile=user,
            muted_user_profile=muted_user,
        )

        url = '/api/v1/users/me/user_mute/' + str(muted_id)
        data = {'muted_user_profile_id': muted_id}
        result = self.api_delete(email, url, data)

        self.assert_json_success(result)
        self.assertNotIn({'id': muted_id, 'name': muted_user.full_name}, get_user_mutes(user))

    def test_muted_user_add_invalid(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        muted_user = self.example_user('cordelia')
        muted_id = muted_user.id
        self.login(email)

        add_user_mute(
            user_profile=user,
            muted_user_profile=muted_user,
        )

        url = '/api/v1/users/me/user_mute/' + str(muted_id)
        data = {'muted_user_profile_id': muted_id}
        result = self.api_put(email, url, data)
        self.assert_json_error(result, "User already muted")

    def test_muted_user_remove_invalid(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        muted_user = self.example_user('cordelia')
        muted_id = muted_user.id
        self.login(email)

        url = '/api/v1/users/me/user_mute/' + str(muted_id)
        data = {'muted_user_profile_id': muted_id}
        result = self.api_delete(email, url, data)
        self.assert_json_error(result, "User is not there in muted_users list")
