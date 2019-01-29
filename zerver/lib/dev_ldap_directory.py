import glob
import logging
import os
from typing import Any, Dict, List, Optional

from django.conf import settings

# See https://jackstromberg.com/2013/01/useraccountcontrol-attributeflag-values/
# for docs on what these values mean.
LDAP_USER_ACCOUNT_CONTROL_NORMAL = '512'
LDAP_USER_ACCOUNT_CONTROL_DISABLED = '514'

def generate_dev_ldap_dir(mode: str, num_users: int=8) -> Dict[str, Dict[str, Any]]:
    mode = mode.lower()
    ldap_data = []
    for i in range(1, num_users+1):
        name = 'LDAP User %d' % (i,)
        email = 'ldapuser%d@zulip.com' % (i,)
        phone_number = '999999999%d' % (i,)
        birthdate = '19%02d-%02d-%02d' % (i, i, i,)
        ldap_data.append((name, email, phone_number, birthdate))

    profile_images = [open(path, "rb").read() for path in
                      glob.glob(os.path.join(settings.STATIC_ROOT, "images/team/*"))]
    ldap_dir = {}
    for i, user_data in enumerate(ldap_data):
        email = user_data[1].lower()
        email_username = email.split('@')[0]
        common_data = {
            'cn': [user_data[0], ],
            'userPassword': [email_username, ],
            'phoneNumber': [user_data[2], ],
            'birthDate': [user_data[3], ],
        }
        if mode == 'a':
            ldap_dir['uid=' + email + ',ou=users,dc=zulip,dc=com'] = dict(
                thumbnailPhoto=[profile_images[i % len(profile_images)], ],
                userAccountControl=[LDAP_USER_ACCOUNT_CONTROL_NORMAL, ],
                **common_data)
        elif mode == 'b':
            ldap_dir['uid=' + email_username + ',ou=users,dc=zulip,dc=com'] = dict(
                jpegPhoto=[profile_images[i % len(profile_images)], ],
                **common_data)
        elif mode == 'c':
            ldap_dir['uid=' + email_username + ',ou=users,dc=zulip,dc=com'] = dict(
                email=email,
                **common_data)

    return ldap_dir

def init_fakeldap(directory: Optional[Dict[str, Dict[str, List[str]]]]=None) -> None:
    # We only use this in development.  Importing mock inside
    # this function is an import time optimization, which
    # avoids the expensive import of the mock module (slow
    # because its dependency pbr uses pkgresources, which is
    # really slow to import.)
    import mock
    from fakeldap import MockLDAP

    # Silent `django_auth_ldap` logger in dev mode to avoid
    # spammy user not found log messages.
    ldap_auth_logger = logging.getLogger('django_auth_ldap')
    ldap_auth_logger.setLevel(logging.CRITICAL)

    fakeldap_logger = logging.getLogger('fakeldap')
    fakeldap_logger.setLevel(logging.CRITICAL)

    ldap_patcher = mock.patch('django_auth_ldap.config.ldap.initialize')
    mock_initialize = ldap_patcher.start()
    mock_ldap = MockLDAP()
    mock_initialize.return_value = mock_ldap

    mock_ldap.directory = directory or generate_dev_ldap_dir(settings.FAKE_LDAP_MODE,
                                                             settings.FAKE_LDAP_NUM_USERS)
