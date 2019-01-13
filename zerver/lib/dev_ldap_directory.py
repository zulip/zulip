import glob
import os
from typing import Any, Dict

from django.conf import settings

# See https://jackstromberg.com/2013/01/useraccountcontrol-attributeflag-values/
# for docs on what these values mean.
LDAP_USER_ACCOUNT_CONTROL_NORMAL = '512'
LDAP_USER_ACCOUNT_CONTROL_DISABLED = '514'

def generate_dev_ldap_dir(mode: str, num_users: int=8) -> Dict[str, Dict[str, Any]]:
    mode = mode.lower()
    names = []
    for i in range(1, num_users+1):
        names.append(('LDAP User %d' % (i,), 'ldapuser%d@zulip.com' % (i,)))

    profile_images = [open(path, "rb").read() for path in
                      glob.glob(os.path.join(settings.STATIC_ROOT, "images/team/*"))]
    ldap_dir = {}
    for i, name in enumerate(names):
        if mode == 'a':
            email = name[1].lower()
            email_username = email.split('@')[0]
            ldap_dir['uid=' + email + ',ou=users,dc=zulip,dc=com'] = {
                'cn': [name[0], ],
                'userPassword':  email_username,
                'thumbnailPhoto': [profile_images[i % len(profile_images)], ],
                'userAccountControl': [LDAP_USER_ACCOUNT_CONTROL_NORMAL, ],
            }
        elif mode == 'b':
            email = name[1].lower()
            email_username = email.split('@')[0]
            ldap_dir['uid=' + email_username + ',ou=users,dc=zulip,dc=com'] = {
                'cn': [name[0], ],
                'userPassword': email_username,
                'jpegPhoto': [profile_images[i % len(profile_images)], ],
            }
        elif mode == 'c':
            email = name[1].lower()
            email_username = email.split('@')[0]
            ldap_dir['uid=' + email_username + ',ou=users,dc=zulip,dc=com'] = {
                'cn': [name[0], ],
                'userPassword': email_username + '_test',
                'email': email,
            }

    return ldap_dir
