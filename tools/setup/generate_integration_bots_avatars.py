#!/usr/bin/env python3
import argparse
import io
import os
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)
from scripts.lib.setup_path import setup_path

setup_path()

os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"
import django

django.setup()

import cairosvg
from PIL import Image

from zerver.lib.integrations import INTEGRATIONS
from zerver.lib.storage import static_path
from zerver.lib.upload.base import DEFAULT_AVATAR_SIZE, resize_avatar


def create_square_image(png: bytes) -> bytes:
    img = Image.open(io.BytesIO(png))
    if img.height == img.width:
        return png

    size = max(img.height, img.width)
    new_img = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
    padding = int(abs(img.height - img.width) / 2)
    position = (0, padding) if img.height < img.width else (padding, 0)
    new_img.paste(img, position)
    out = io.BytesIO()
    new_img.save(out, format="png")
    return out.getvalue()


def create_integration_bot_avatar(logo_path: str, bot_avatar_path: str) -> None:
    if logo_path.endswith(".svg"):
        avatar = cairosvg.svg2png(
            url=logo_path, output_width=DEFAULT_AVATAR_SIZE, output_height=DEFAULT_AVATAR_SIZE
        )
    else:
        with open(logo_path, "rb") as f:
            image = f.read()
        square_image = create_square_image(image)
        avatar = resize_avatar(square_image)

    os.makedirs(os.path.dirname(bot_avatar_path), exist_ok=True)
    with open(bot_avatar_path, "wb") as f:
        f.write(avatar)


def generate_integration_bots_avatars(check_missing: bool = False) -> None:
    missing = set()
    for integration in INTEGRATIONS.values():
        if not integration.logo_path:
            continue

        bot_avatar_path = integration.get_bot_avatar_path()
        if bot_avatar_path is None:
            continue

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
