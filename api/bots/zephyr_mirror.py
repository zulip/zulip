#!/usr/bin/python
import sys
import subprocess
import time
import optparse
import os
import traceback

from zephyr_mirror_backend import parse_args

(options, args) = parse_args()

args = [os.path.join(options.root_path, "user_root", "zephyr_mirror_backend.py")]
args.extend(sys.argv[1:])

if options.sync_subscriptions:
    subprocess.call(args)
    sys.exit(0)

while True:
    print "Starting zephyr mirroring bot"
    try:
        subprocess.call(args)
    except:
        traceback.print_exc()
    time.sleep(1)
