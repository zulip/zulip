#!/usr/bin/env python3

import glob
import os
import sys
import shutil
import tempfile
from typing import List, Optional

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)
from scripts.lib.setup_path import setup_path
setup_path()

from zulip_bots.lib import get_bots_directory_path

def generate_zulip_bots_static_files() -> None:
    bots_dir = 'static/generated/bots'
    if os.path.isdir(bots_dir):
        # delete old static files, they could be outdated
        shutil.rmtree(bots_dir)

    os.makedirs(bots_dir, exist_ok=True)

    def copyfiles(paths: List[str]) -> None:
        for src_path in paths:
            bot_name = os.path.basename(os.path.dirname(src_path))

            bot_dir = os.path.join(bots_dir, bot_name)
            os.makedirs(bot_dir, exist_ok=True)

            dst_path = os.path.join(bot_dir, os.path.basename(src_path))
            if not os.path.isfile(dst_path):
                shutil.copyfile(src_path, dst_path)

    package_bots_dir = get_bots_directory_path()

    logo_glob_pattern = os.path.join(package_bots_dir, '*/logo.*')
    logos = glob.glob(logo_glob_pattern)
    copyfiles(logos)

    doc_glob_pattern = os.path.join(package_bots_dir, '*/doc.md')
    docs = glob.glob(doc_glob_pattern)
    copyfiles(docs)

def create_png_from_svg(svg_path: str, destination_dir: Optional[str]=None) -> str:
    import cairosvg

    png_name = os.path.splitext(os.path.basename(svg_path))[0] + '.png'
    if destination_dir is None:
        destination_dir = tempfile.gettempdir()
    png_path = os.path.join(destination_dir, png_name)
    cairosvg.svg2png(url=svg_path, write_to=png_path)
    return png_path

if __name__ == "__main__":
    generate_zulip_bots_static_files()
