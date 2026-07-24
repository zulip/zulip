import os
import pwd
import sys

from scripts.lib.zulip_tools import is_zulip_production_install


def check_venv(filename: str) -> None:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Mirror scripts/lib/setup_path.py: honor venv-override env vars; skip on production.
    if is_zulip_production_install():
        venv_override = None
    else:
        venv_override = os.environ.get("UV_PROJECT_ENVIRONMENT") or os.environ.get("VIRTUAL_ENV")
    venv = os.path.realpath(os.path.join(BASE_DIR, venv_override or ".venv"))
    if sys.prefix == venv:
        return
    # Activate the resolved venv in-process (mirrors setup_path.py).
    activate_this = os.path.join(venv, "bin", "activate_this.py")
    if os.path.exists(activate_this):
        with open(activate_this) as f:
            exec(f.read(), {"__file__": activate_this})  # noqa: S102
        return

    print(f"You need to run {filename} inside a Zulip dev environment.")
    user_id = os.getuid()
    user_name = pwd.getpwuid(user_id).pw_name

    print(f"You can `source {venv}/bin/activate` to enter the development environment.")

    if user_name not in ("vagrant", "zulipdev"):
        print()
        print("If you are using Vagrant, first run `vagrant ssh` to enter the Vagrant guest.")
    sys.exit(1)
