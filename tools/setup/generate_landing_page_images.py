#!/usr/bin/env python3
"""Generates versions of landing page images to be served in different conditions."""

import glob
import os
import sys
from pathlib import Path

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

import pyvips

LANDING_IMAGES_DIR = os.path.join(ZULIP_PATH, "static", "images", "landing-page", "hello")
ORIGINAL_IMAGES_DIR = os.path.join(LANDING_IMAGES_DIR, "original")
GENERATED_IMAGES_DIR = os.path.join(LANDING_IMAGES_DIR, "generated")


def get_x_size(size: int, x: int) -> int:
    return int(x / 3.0 * size)


def generate_landing_page_images() -> None:
    if not os.path.exists(GENERATED_IMAGES_DIR):
        os.mkdir(GENERATED_IMAGES_DIR)
    else:
        # Delete folder contents to avoid stale images between different versions of the script.
        for file in os.listdir(GENERATED_IMAGES_DIR):
            os.remove(os.path.join(GENERATED_IMAGES_DIR, file))

    for image_file_path in glob.glob(f"{ORIGINAL_IMAGES_DIR}/*"):
        file_name = Path(image_file_path).stem
        image = pyvips.Image.new_from_file(image_file_path)
        size = 2
        scaled_width = get_x_size(image.width, size)
        scaled_height = get_x_size(image.height, size)
        scaled = image.thumbnail_image(scaled_width, height=scaled_height)
        for format in ("webp[Q=60]", "jpg[Q=80,optimize-coding=true]"):
            scaled.write_to_file(f"{GENERATED_IMAGES_DIR}/{file_name}-{size}x.{format}")


if __name__ == "__main__":
    generate_landing_page_images()
