#!/usr/bin/env python3

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

import tempfile
from typing import Optional

import io
import cairosvg
from PIL import Image

from zerver.lib.upload import resize_avatar, DEFAULT_AVATAR_SIZE
from zerver.lib.integrations import Integration, WEBHOOK_INTEGRATIONS
from zerver.lib.storage import static_path

def create_png_from_svg(svg_path: str, destination_dir: Optional[str]=None) -> str:
    png_name = os.path.splitext(os.path.basename(svg_path))[0] + '.png'
    if destination_dir is None:
        destination_dir = tempfile.gettempdir()
    png_path = os.path.join(destination_dir, png_name)
    cairosvg.svg2png(url=svg_path, write_to=png_path)
    return png_path

def create_square_image(png: bytes) -> bytes:
    img = Image.open(io.BytesIO(png))
    if img.height == img.width:
        return png

    size = max(img.height, img.width)
    new_img = Image.new("RGBA", (size, size), color=None)
    padding = int(abs(img.height - img.width) / 2)
    position = (0, padding) if img.height < img.width else (padding, 0)
    new_img.paste(img, position)
    out = io.BytesIO()
    new_img.save(out, format='png')
    return out.getvalue()

def create_integration_bot_avatar(logo_path: str) -> None:
    if logo_path.endswith('.svg'):
        avatar = cairosvg.svg2png(
            url=logo_path, output_width=DEFAULT_AVATAR_SIZE, output_height=DEFAULT_AVATAR_SIZE)
    else:
        with open(logo_path, 'rb') as f:
            image = f.read()
        square_image = create_square_image(image)
        avatar = resize_avatar(square_image)

    name = os.path.splitext(os.path.basename(logo_path))[0]
    bot_avatar_path = os.path.join(
        ZULIP_PATH, 'static', Integration.DEFAULT_BOT_AVATAR_PATH.format(name=name))
    os.makedirs(os.path.dirname(bot_avatar_path), exist_ok=True)
    with open(bot_avatar_path, 'wb') as f:
        f.write(avatar)

def generate_integration_bots_avatars() -> None:
    for webhook in WEBHOOK_INTEGRATIONS:
        logo_path = webhook.get_logo_path()
        if not logo_path:
            continue
        create_integration_bot_avatar(static_path(logo_path))

if __name__ == '__main__':
    generate_integration_bots_avatars()
