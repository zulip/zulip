import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm
from zerver.models.users import get_user

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class ZephyrTest(ZulipTestCase):
    def test_webathena_kerberos_login(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        def post(subdomain: Any, **kwargs: Any) -> "TestHttpResponse":
            params = {k: orjson.dumps(v).decode() for k, v in kwargs.items()}
            return self.client_post(
                "/accounts/webathena_kerberos_login/", params, subdomain=subdomain
            )

        result = post("zulip")
        self.assert_json_error(result, "Could not find Kerberos credential")

        result = post("zulip", cred="whatever")
        self.assert_json_error(result, "Webathena login not enabled")

        email = str(self.mit_email("starnine"))
        realm = get_realm("zephyr")
        user = get_user(email, realm)
        api_key = user.api_key
        self.login_user(user)

        def ccache_mock(**kwargs: Any) -> Any:
            return patch("zerver.views.zephyr.make_ccache", **kwargs)

        def ssh_mock(**kwargs: Any) -> Any:
            return patch("zerver.views.zephyr.subprocess.check_call", **kwargs)

        def mirror_mock() -> Any:
            return self.settings(PERSONAL_ZMIRROR_SERVER="server")

        cred = dict(cname=dict(nameString=["starnine"]))

        with ccache_mock(side_effect=KeyError("foo")):
            result = post("zephyr", cred=cred)
        self.assert_json_error(result, "Invalid Kerberos cache")

        with (
            ccache_mock(return_value=b"1234"),
            ssh_mock(side_effect=subprocess.CalledProcessError(1, [])),
            mirror_mock(),
            self.assertLogs(level="ERROR") as log,
        ):
            result = post("zephyr", cred=cred)

        self.assert_json_error(result, "We were unable to set up mirroring for you")
        self.assertIn("Error updating the user's ccache", log.output[0])

        with ccache_mock(return_value=b"1234"), self.assertLogs(level="ERROR") as log:
            result = post("zephyr", cred=cred)

        self.assert_json_error(result, "We were unable to set up mirroring for you")
        self.assertIn("PERSONAL_ZMIRROR_SERVER is not properly configured", log.output[0])

        with ccache_mock(return_value=b"1234"), mirror_mock(), ssh_mock() as ssh:
            result = post("zephyr", cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with(
            [
                "ssh",
                "server",
                "--",
                f"/home/zulip/python-zulip-api/zulip/integrations/zephyr/process_ccache starnine {api_key} MTIzNA==",
            ]
        )

        # Accounts whose Kerberos usernames are known not to match their
        # zephyr accounts are hardcoded, and should be handled properly.

        def kerberos_alter_egos_mock() -> Any:
            return patch(
                "zerver.views.zephyr.kerberos_alter_egos", {"kerberos_alter_ego": "starnine"}
            )

        cred = dict(cname=dict(nameString=["kerberos_alter_ego"]))
        with (
            ccache_mock(return_value=b"1234"),
            mirror_mock(),
            ssh_mock() as ssh,
            kerberos_alter_egos_mock(),
        ):
            result = post("zephyr", cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with(
            [
                "ssh",
                "server",
                "--",
                f"/home/zulip/python-zulip-api/zulip/integrations/zephyr/process_ccache starnine {api_key} MTIzNA==",
            ]
        )
