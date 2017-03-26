from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user_profile_by_email

class ZephyrTest(ZulipTestCase):
    def test_webathena_kerberos_login(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        def post(**kwargs):
            # type: (**Any) -> HttpResponse
            params = {k: ujson.dumps(v) for k, v in kwargs.items()}
            return self.client_post('/accounts/webathena_kerberos_login/', params)

        result = post()
        self.assert_json_error(result, 'Could not find Kerberos credential')

        result = post(cred='whatever')
        self.assert_json_error(result, 'Webathena login not enabled')

        email = 'starnine@mit.edu'
        self.login(email)

        def ccache_mock(**kwargs):
            # type: (**Any) -> Any
            return patch('zerver.views.zephyr.make_ccache', **kwargs)

        def ssh_mock(**kwargs):
            # type: (**Any) -> Any
            return patch('zerver.views.zephyr.subprocess.check_call', **kwargs)

        def mirror_mock():
            # type: () -> Any
            return self.settings(PERSONAL_ZMIRROR_SERVER='server')

        def logging_mock():
            # type: () -> Any
            return patch('logging.exception')

        cred = dict(cname=dict(nameString=['starnine']))

        with ccache_mock(side_effect=KeyError('foo')):
            result = post(cred=cred)
        self.assert_json_error(result, 'Invalid Kerberos cache')

        with \
                ccache_mock(return_value=b'1234'), \
                ssh_mock(side_effect=KeyError('foo')), \
                logging_mock() as log:
            result = post(cred=cred)

        self.assert_json_error(result, 'We were unable to setup mirroring for you')
        log.assert_called_with("Error updating the user's ccache")

        with ccache_mock(return_value=b'1234'), mirror_mock(), ssh_mock() as ssh:
            result = post(cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with([
            'ssh',
            'server',
            '--',
            '/home/zulip/zulip/bots/process_ccache',
            'starnine',
            get_user_profile_by_email(email).api_key,
            'MTIzNA=='])

        # Accounts whose Kerberos usernames are known not to match their
        # zephyr accounts are hardcoded, and should be handled properly.

        def kerberos_alter_egos_mock():
            # type: () -> Any
            return patch(
                'zerver.views.zephyr.kerberos_alter_egos',
                {'kerberos_alter_ego': 'starnine'})

        cred = dict(cname=dict(nameString=['kerberos_alter_ego']))
        with \
                ccache_mock(return_value=b'1234'), \
                mirror_mock(), \
                ssh_mock() as ssh, \
                kerberos_alter_egos_mock():
            result = post(cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with([
            'ssh',
            'server',
            '--',
            '/home/zulip/zulip/bots/process_ccache',
            'starnine',
            get_user_profile_by_email(email).api_key,
            'MTIzNA=='])
