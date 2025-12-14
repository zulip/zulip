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

    @override_settings(DEVELOPMENT=False, PRODUCTION=True)
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

    def test_checks_external_host_value(self) -> None:
        self.assert_check_with_error(None, EXTERNAL_HOST="testserver.local")
        self.assert_check_with_error(None, EXTERNAL_HOST="testserver.local:443")
        self.assert_check_with_error(None, EXTERNAL_HOST="testserver.local:https")

        self.assert_check_with_error(
            re.compile(r"EXTERNAL_HOST \(\S+\) is too long"),
            EXTERNAL_HOST=("a234567890." * 25 + "local"),
        )

        self.assert_check_with_error(
            re.compile(
                r"\(zulip\.E002\) EXTERNAL_HOST \(\S+\) contains non-ASCII characters\n.*xn--wgv71a119e\.example\.com"
            ),
            EXTERNAL_HOST="日本語.example.com",
        )

        self.assert_check_with_error(
            "EXTERNAL_HOST (-bogus-.example.com) does not validate as a hostname",
            EXTERNAL_HOST="-bogus-.example.com:443",
        )

    def test_checks_auth(self) -> None:
        self.assert_check_with_error(
            (
                'SOCIAL_AUTH_SAML_ENABLED_IDPS["idp_name"]["extra_attrs"]: '
                "(zulip.E003) zulip_groups can't be listed in extra_attrs"
            ),
            SOCIAL_AUTH_SAML_ENABLED_IDPS={
                "idp_name": {
                    "entity_id": "https://idp.testshib.org/idp/shibboleth",
                    "url": "https://idp.testshib.org/idp/profile/SAML2/Redirect/SSO",
                    "attr_user_permanent_id": "email",
                    "attr_first_name": "first_name",
                    "attr_last_name": "last_name",
                    "attr_username": "email",
                    "attr_email": "email",
                    "extra_attrs": ["title", "mobilePhone", "zulip_role", "zulip_groups"],
                }
            },
        )

        self.assert_check_with_error(
            (
                'settings.SOCIAL_AUTH_SYNC_ATTRS_DICT["example_org"]["saml"]["custom__groups"]: '
                "(zulip.E004) zulip_groups can't be listed as a SAML attribute"
            ),
            SOCIAL_AUTH_SYNC_ATTRS_DICT={
                "example_org": {
                    "saml": {
                        "role": "zulip_role",
                        "custom__groups": "zulip_groups",
                        "custom__title": "title",
                        "groups": ["group1", "group2", ("samlgroup3", "zulipgroup3"), "group4"],
                    }
                }
            },
        )
