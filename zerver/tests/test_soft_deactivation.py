# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib.soft_deactivation import (
    do_soft_deactivate_user,
    do_soft_deactivate_users
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

class UserSoftDeactivationTests(ZulipTestCase):

    def test_do_soft_deactivate_user(self):
        # type: () -> None
        user = self.example_user('hamlet')
        self.assertFalse(user.long_term_idle)

        do_soft_deactivate_user(user)

        user.refresh_from_db()
        self.assertTrue(user.long_term_idle)

    def test_do_soft_deactivate_users(self):
        # type: () -> None
        users = [
            self.example_user('hamlet'),
            self.example_user('iago'),
            self.example_user('cordelia'),
        ]
        for user in users:
            self.assertFalse(user.long_term_idle)

        do_soft_deactivate_users(users)

        for user in users:
            user.refresh_from_db()
            self.assertTrue(user.long_term_idle)
