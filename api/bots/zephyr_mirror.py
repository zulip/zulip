#!/usr/bin/python
import sys
import subprocess
import time
import optparse
import os
import traceback

from zephyr_mirror_backend import parse_args

(options, args) = parse_args()

while True:
    print "Starting zephyr mirroring bot"
    try:
        args = [os.path.join(options.root_path, "user_root", "zephyr_mirror_backend.py")]
        args.extend(sys.argv[1:])
        subprocess.call(args)
    except:
        traceback.print_exc()
    time.sleep(1)
