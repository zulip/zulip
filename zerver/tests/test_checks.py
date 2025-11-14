import os
import re
from contextlib import ExitStack
from typing import Any

from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase


class TestChecks(ZulipTestCase):
    def assert_check_with_error(self, test: re.Pattern[str] | str | None, **kwargs: Any) -> None:
        with open(os.devnull, "w") as DEVNULL, override_settings(**kwargs), ExitStack() as stack:
            if isinstance(test, str):
                stack.enter_context(self.assertRaisesMessage(SystemCheckError, test))
            elif isinstance(test, re.Pattern):
                stack.enter_context(self.assertRaisesRegex(SystemCheckError, test))
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

    def test_checks_external_host_domain(self) -> None:
        message_re = r"\(zulip\.E002\) EXTERNAL_HOST \(\S+\) does not contain a domain part"
        try:
            # We default to skippping this check in CI, because
            # "testserver" is part of so many tests.  We temporarily
            # strip out the environment variable we use to detect
            # that, so we can trigger the check.
            del os.environ["ZULIP_TEST_SUITE"]

            self.assert_check_with_error(None, EXTERNAL_HOST="server-1.local")

            self.assert_check_with_error(
                re.compile(rf"{message_re}\s*HINT: Add .local to the end"), EXTERNAL_HOST="server-1"
            )

            self.assert_check_with_error(
                re.compile(rf"{message_re}\s*HINT: Add .localdomain to the end"),
                EXTERNAL_HOST="localhost",
            )

        finally:
            os.environ["ZULIP_TEST_SUITE"] = "true"
