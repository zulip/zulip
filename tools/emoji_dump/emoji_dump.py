#!/usr/bin/env python2.7
from __future__ import print_function
import os
import shutil
import subprocess
import json
import sys

from PIL import Image, ImageDraw, ImageFont

class MissingGlyphError(Exception):
    pass


def color_font(name, code_point):
    in_name = 'bitmaps/strike1/uni{}.png'.format(code_point)
    out_name = 'out/unicode/{}.png'.format(code_point)
    try:
        shutil.copyfile(in_name, out_name)
    except IOError:
        raise MissingGlyphError('name: %r code_point: %r' % (name, code_point))


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
    image.resize(SIZE, Image.ANTIALIAS).save('out/unicode/{}.png'.format(code_point), 'PNG')


# ttx is in the fonttools pacakge, the -z option is only on master
# https://github.com/behdad/fonttools/

# NotoColorEmoji.tff is from
# https://android.googlesource.com/platform/external/noto-fonts/+/kitkat-release/NotoColorEmoji.ttf
subprocess.call('ttx -v -z extfile NotoColorEmoji.ttf', shell=True)

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
for name, code_point in emoji_map.items():
    try:
        color_font(name, code_point)
    except MissingGlyphError:
        try:
            bw_font(name, code_point)
        except Exception as e:
            print(e)
            print('Missing {}, {}'.format(name, code_point))
            failed = True
            continue

    os.symlink('unicode/{}.png'.format(code_point), 'out/{}.png'.format(name))

if failed:
    print("Errors dumping emoji!")
    sys.exit(1)
