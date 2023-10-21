#!/usr/bin/env python3
"""Generates versions of landing page images to be served in different conditions."""

import glob
import os
import sys
from pathlib import Path
from typing import Tuple

from PIL import Image

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

LANDING_IMAGES_DIR = os.path.join(ZULIP_PATH, "static", "images", "landing-page", "hello")
ORIGINAL_IMAGES_DIR = os.path.join(LANDING_IMAGES_DIR, "original")
GENERATED_IMAGES_DIR = os.path.join(LANDING_IMAGES_DIR, "generated")


def get_x_size(size: Tuple[float, float], x: int) -> Tuple[int, int]:
    return int(x / 3 * size[0]), int(x / 3 * size[1])


def generate_landing_page_images() -> None:
    if not os.path.exists(GENERATED_IMAGES_DIR):
        os.mkdir(GENERATED_IMAGES_DIR)

    for image_file_path in glob.glob(f"{ORIGINAL_IMAGES_DIR}/*"):
        file_name = Path(image_file_path).stem
        with Image.open(image_file_path) as image:
            size_2x = get_x_size(image.size, 2)
            size_1x = get_x_size(image.size, 1)

            ## Generate WEBP images.
            image.save(f"{GENERATED_IMAGES_DIR}/{file_name}-3x.webp", quality=50)
            image_2x = image.resize(size_2x)
            image_2x.save(f"{GENERATED_IMAGES_DIR}/{file_name}-2x.webp", quality=50)
            image_1x = image.resize(size_1x)
            image_1x.save(f"{GENERATED_IMAGES_DIR}/{file_name}-1x.webp", quality=70)

            ## Generate JPG images.
            # Convert from RGBA to RGB since jpg doesn't support transparency.
            rgb_image = image.convert("RGB")
            rgb_image.save(f"{GENERATED_IMAGES_DIR}/{file_name}-3x.jpg", quality=19, optimize=True)
            rgb_image_2x = rgb_image.resize(size_2x)
            rgb_image_2x.save(
                f"{GENERATED_IMAGES_DIR}/{file_name}-2x.jpg", quality=50, optimize=True
            )
            rgb_image_1x = rgb_image.resize(size_1x)
            rgb_image_1x.save(
                f"{GENERATED_IMAGES_DIR}/{file_name}-1x.jpg", quality=70, optimize=True
            )


if __name__ == "__main__":
    generate_landing_page_images()
