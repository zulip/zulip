#!/usr/bin/env python
from __future__ import print_function
import os
import glob
import shutil
import subprocess
import json
import sys
import xml.etree.ElementTree as ET
from six import unichr

from PIL import Image, ImageDraw, ImageFont

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../')

EMOJI_DUMP_DIR_PATH = os.path.join(ZULIP_PATH, 'var', 'emoji_dump')

class MissingGlyphError(Exception):
    pass


def color_font(code_point, code_point_to_fname_map):
    in_name = os.path.join(EMOJI_DUMP_DIR_PATH, 'bitmaps/strike0/{}.png'.format(
        code_point_to_fname_map[int(code_point, 16)]
    ))
    out_name = 'out/unicode/{}.png'.format(code_point)
    try:
        shutil.copyfile(in_name, out_name)
    except IOError:
        raise MissingGlyphError('code_point: %r' % (code_point))


def bw_font(name, code_point):
    char = unichr(int(code_point, 16))

    AA_SCALE = 8
    SIZE = (68, 68)
    BIG_SIZE = tuple([x * AA_SCALE for x in SIZE])

    # AndroidEmoji.ttf is from
    # https://android.googlesource.com/platform/frameworks/base.git/+/master/data/fonts/AndroidEmoji.ttf
    # commit 07912f876c8639f811b06831465c14c4a3b17663
    font = ImageFont.truetype('AndroidEmoji.ttf', 65 * AA_SCALE)
    image = Image.new('RGBA', BIG_SIZE)
    draw = ImageDraw.Draw(image)
    draw.text((0, 0), char, font=font, fill='black')
    image.resize(SIZE, Image.ANTIALIAS).save(
        'out/unicode/{}.png'.format(code_point), 'PNG'
    )


def code_point_to_file_name_map(ttx):
    """Given the NotoColorEmoji.ttx file, parse it to generate a map from
    codepoint to filename (a la glyph0****.png)
    """
    result = {}
    xml = ET.parse(ttx)
    for elem in xml.find("*cmap_format_12"): # type: ignore # https://github.com/python/typeshed/pull/254
        code_point = int(elem.attrib["code"], 16)
        fname = elem.attrib["name"]
        result[code_point] = fname
    return result


def main():
    # ttx is in the fonttools pacakge, the -z option is only on master
    # https://github.com/behdad/fonttools/

    # NotoColorEmoji.tff is from
    # https://android.googlesource.com/platform/external/noto-fonts/+/marshmallow-release/other/NotoColorEmoji.ttf
    # note that you have to run it though base64 -D before being able
    # to use it, since it downloads from that page base64 encoded

    # this is so we don't accidently leave ttx files from previous
    # runs of this script lying around
    for fname in glob.glob(os.path.join(EMOJI_DUMP_DIR_PATH, "*ttx*")):
        os.remove(fname)

    # check if directory `var/emoji_dump` exists
    subprocess.check_call(['mkdir', '-p', EMOJI_DUMP_DIR_PATH])

    subprocess.call('ttx -v -z extfile -d {} NotoColorEmoji.ttf'.format(EMOJI_DUMP_DIR_PATH), shell=True)

    try:
        shutil.rmtree('out')
    except OSError:
        pass

    os.mkdir('out')
    os.mkdir('out/unicode')

    emoji_map = json.load(open('emoji_map.json'))

    # Fix data problem with red/blue cars being inaccurate.
    emoji_map['blue_car'] = emoji_map['red_car']
    emoji_map['red_car'] = emoji_map['oncoming_automobile']

    failed = False
    code_point_to_fname_map = code_point_to_file_name_map(os.path.join(EMOJI_DUMP_DIR_PATH, "NotoColorEmoji.ttx"))
    for name, code_point in emoji_map.items():
        try:
            color_font(code_point, code_point_to_fname_map)
        except MissingGlyphError:
            try:
                bw_font(name, code_point)
            except Exception as e:
                print(e)
                print('Missing {}, {}'.format(name, code_point))
                failed = True
                continue

        os.symlink(
            'unicode/{}.png'.format(code_point),
            'out/{}.png'.format(name)
        )

    if failed:
        print("Errors dumping emoji!")
        sys.exit(1)


if __name__ == "__main__":
    main()
