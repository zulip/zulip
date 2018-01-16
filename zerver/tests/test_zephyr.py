
import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user, get_realm


class ZephyrTest(ZulipTestCase):
    def test_webathena_kerberos_login(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        def post(subdomain: Any, **kwargs: Any) -> HttpResponse:
            params = {k: ujson.dumps(v) for k, v in kwargs.items()}
            return self.client_post('/accounts/webathena_kerberos_login/', params,
                                    subdomain=subdomain)

        result = post("zulip")
        self.assert_json_error(result, 'Could not find Kerberos credential')

        result = post("zulip", cred='whatever')
        self.assert_json_error(result, 'Webathena login not enabled')

        email = str(self.mit_email("starnine"))
        realm = get_realm('zephyr')
        self.login(email, realm=realm)

        def ccache_mock(**kwargs: Any) -> Any:
            return patch('zerver.views.zephyr.make_ccache', **kwargs)

        def ssh_mock(**kwargs: Any) -> Any:
            return patch('zerver.views.zephyr.subprocess.check_call', **kwargs)

        def mirror_mock() -> Any:
            return self.settings(PERSONAL_ZMIRROR_SERVER='server')

        def logging_mock() -> Any:
            return patch('logging.exception')

        cred = dict(cname=dict(nameString=['starnine']))

        with ccache_mock(side_effect=KeyError('foo')):
            result = post("zephyr", cred=cred)
        self.assert_json_error(result, 'Invalid Kerberos cache')

        with \
                ccache_mock(return_value=b'1234'), \
                ssh_mock(side_effect=KeyError('foo')), \
                logging_mock() as log:
            result = post("zephyr", cred=cred)

        self.assert_json_error(result, 'We were unable to setup mirroring for you')
        log.assert_called_with("Error updating the user's ccache")

        with ccache_mock(return_value=b'1234'), mirror_mock(), ssh_mock() as ssh:
            result = post("zephyr", cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with([
            'ssh',
            'server',
            '--',
            '/home/zulip/python-zulip-api/zulip/integrations/zephyr/process_ccache',
            'starnine',
            get_user(email, realm).api_key,
            'MTIzNA=='])

        # Accounts whose Kerberos usernames are known not to match their
        # zephyr accounts are hardcoded, and should be handled properly.

        def kerberos_alter_egos_mock() -> Any:
            return patch(
                'zerver.views.zephyr.kerberos_alter_egos',
                {'kerberos_alter_ego': 'starnine'})

        cred = dict(cname=dict(nameString=['kerberos_alter_ego']))
        with \
                ccache_mock(return_value=b'1234'), \
                mirror_mock(), \
                ssh_mock() as ssh, \
                kerberos_alter_egos_mock():
            result = post("zephyr", cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with([
            'ssh',
            'server',
            '--',
            '/home/zulip/python-zulip-api/zulip/integrations/zephyr/process_ccache',
            'starnine',
            get_user(email, realm).api_key,
            'MTIzNA=='])
