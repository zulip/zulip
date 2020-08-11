import os
import pwd
import sys


def check_venv(filename: str) -> None:
    if os.path.basename(sys.prefix) != "zulip-py3-venv":
        print(f"You need to run {filename} inside a Zulip dev environment.")
        user_id = os.getuid()
        user_name = pwd.getpwuid(user_id).pw_name
        if user_name != 'vagrant' and user_name != 'zulipdev':
            print("If you are using Vagrant, you can `vagrant ssh` to enter the Vagrant guest.")
        else:
            print("You can `source /srv/zulip-py3-venv/bin/activate` "
                  "to enter the Zulip development environment.")
        sys.exit(1)
