import os
from contextlib import ExitStack
from typing import Any

from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase


class TestChecks(ZulipTestCase):
    def assert_check_with_error(self, message: str | None, **kwargs: Any) -> None:
        with open(os.devnull, "w") as DEVNULL, override_settings(**kwargs), ExitStack() as stack:
            if message is not None:
                stack.enter_context(self.assertRaisesMessage(SystemCheckError, message))
            call_command("check", stdout=DEVNULL)

    def test_checks_required_setting(self) -> None:
        self.assert_check_with_error(
            "(zulip.E001) You must set ZULIP_ADMINISTRATOR in /etc/zulip/settings.py",
            ZULIP_ADMINISTRATOR="zulip-admin@example.com",
        )

        self.assert_check_with_error(
            "(zulip.E001) You must set ZULIP_ADMINISTRATOR in /etc/zulip/settings.py",
            ZULIP_ADMINISTRATOR="",
        )

        self.assert_check_with_error(
            "(zulip.E001) You must set ZULIP_ADMINISTRATOR in /etc/zulip/settings.py",
            ZULIP_ADMINISTRATOR=None,
        )

        self.assert_check_with_error(
            None,
            ZULIP_ADMINISTRATOR="other-admin-email@example.com",
        )
