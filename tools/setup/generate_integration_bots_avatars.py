#!/usr/bin/env python3

import os
import sys
import tempfile
from typing import Optional

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)
from scripts.lib.setup_path import setup_path
setup_path()

import cairosvg

def create_png_from_svg(svg_path: str, destination_dir: Optional[str]=None) -> str:
    png_name = os.path.splitext(os.path.basename(svg_path))[0] + '.png'
    if destination_dir is None:
        destination_dir = tempfile.gettempdir()
    png_path = os.path.join(destination_dir, png_name)
    cairosvg.svg2png(url=svg_path, write_to=png_path)
    return png_path
