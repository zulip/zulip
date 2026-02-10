import os
import pwd
import sys


def check_venv(filename: str) -> None:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    venv = os.path.realpath(os.path.join(BASE_DIR, ".venv"))
    if sys.prefix != venv:
        print(f"You need to run {filename} inside a Zulip dev environment.")
        user_id = os.getuid()
        user_name = pwd.getpwuid(user_id).pw_name

        print(f"You can `source {venv}/bin/activate` to enter the development environment.")

        if user_name not in ("vagrant", "zulipdev"):
            print()
            print("If you are using Vagrant, first run `vagrant ssh` to enter the Vagrant guest.")
        sys.exit(1)
