#!/usr/bin/env -S uv run --frozen --no-config --preview-features=target-workspace-discovery --script  # -*-python-*-
import argparse
import os
import sys

import django
import pyvips

os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"
django.setup()

from zerver.lib.integrations import INTEGRATIONS
from zerver.lib.storage import static_path
from zerver.lib.thumbnail import DEFAULT_AVATAR_SIZE

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_integration_bot_avatar(logo_path: str, bot_avatar_path: str) -> None:
    os.makedirs(os.path.dirname(bot_avatar_path), exist_ok=True)
    avatar = pyvips.Image.thumbnail(logo_path, DEFAULT_AVATAR_SIZE, height=DEFAULT_AVATAR_SIZE)
    if avatar.height != avatar.width:
        avatar = avatar.gravity(
            pyvips.CompassDirection.CENTRE, DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE
        )
    avatar.write_to_file(bot_avatar_path)


def generate_integration_bots_avatars(check_missing: bool = False) -> None:
    missing = set()
    for integration in INTEGRATIONS.values():
        if not integration.is_enabled_in_catalog():
            continue
        bot_avatar_path = integration.get_bot_avatar_path()
        bot_avatar_path = os.path.join(ZULIP_PATH, "static", bot_avatar_path)
        if check_missing:
            if not os.path.isfile(bot_avatar_path):
                missing.add(integration.name)
        else:
            create_integration_bot_avatar(static_path(integration.logo_path), bot_avatar_path)

    if missing:
        print(
            "ERROR: Bot avatars are missing for these webhooks: {}.\n"
            "ERROR: Run ./tools/setup/generate_integration_bots_avatars.py "
            "to generate them.\nERROR: Commit the newly generated avatars to "
            "the repository.".format(", ".join(missing))
        )
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-missing", action="store_true")
    options = parser.parse_args()
    generate_integration_bots_avatars(options.check_missing)
