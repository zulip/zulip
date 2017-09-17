#!/usr/bin/env python3

import glob
import os
import sys
import shutil

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)

from typing import List, Text
from zproject import settings
from zulip_bots.lib import get_bots_directory_path


bots_dir = os.path.join(settings.STATIC_ROOT, 'generated/bots')
if not os.path.isdir(bots_dir):
    os.makedirs(bots_dir)

def copyfiles(paths):
    # type: (List[Text]) -> None
    for src_path in paths:
        bot_name = os.path.basename(os.path.dirname(src_path))

        bot_dir = os.path.join(bots_dir, bot_name)
        if not os.path.isdir(bot_dir):
            os.mkdir(bot_dir)

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
