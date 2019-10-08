import os
import pwd
import sys

def check_venv(filename):
    # type: (str) -> None
    try:
        import django
        import ujson
        import zulip
    except ImportError:
        print("You need to run %s inside a Zulip dev environment." % (filename,))
        user_id = os.getuid()
        user_name = pwd.getpwuid(user_id).pw_name
        if user_name != 'vagrant' and user_name != 'zulipdev':
            print("If you are using Vagrant, you can `vagrant ssh` to enter the Vagrant guest.")
        else:
            print("You can `source /srv/zulip-py3-venv/bin/activate` "
                  "to enter the Zulip development environment.")
        sys.exit(1)
