"""
Use libraries from a virtualenv (by modifying sys.path) in production.
"""

import os
import sys


def setup_path() -> None:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    venv = os.path.realpath(os.path.join(BASE_DIR, ".venv"))
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        virtual_env = os.path.realpath(virtual_env)
        if os.path.isdir(virtual_env):
            venv = virtual_env

    def get_site_packages_path(venv_path: str) -> str:
        python_version = "python{}.{}".format(*sys.version_info[:2])
        return os.path.join(venv_path, "lib", python_version, "site-packages")

    if sys.prefix != venv:
        sys.path = list(
            filter(
                # zulip-py3-venv was an historical virtualenv symlink
                lambda p: "/zulip-py3-venv/" not in p and "/.venv/" not in p,
                sys.path,
            )
        )
        activate_this = os.path.join(venv, "bin", "activate_this.py")
        if os.path.exists(activate_this):
            activate_locals = dict(__file__=activate_this)
            with open(activate_this) as f:
                exec(f.read(), activate_locals)  # noqa: S102
        else:
            site_packages = get_site_packages_path(venv)
            if not os.path.exists(site_packages):
                fallback_venv = os.path.realpath(os.path.join(BASE_DIR, ".venv"))
                fallback_site_packages = get_site_packages_path(fallback_venv)
                if os.path.exists(fallback_site_packages):
                    venv = fallback_venv
                    site_packages = fallback_site_packages
            if not os.path.exists(site_packages):
                raise RuntimeError(venv + " is not configured for this Python version")
            sys.path.insert(0, site_packages)
        # Check that the python version running this function
        # is same as python version that created the virtualenv.
        python_version = "python{}.{}".format(*sys.version_info[:2])
        if not os.path.exists(os.path.join(venv, "lib", python_version)):
            raise RuntimeError(venv + " was not set up for this Python version")
