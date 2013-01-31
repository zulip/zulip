#!/usr/bin/python
# Copyright (C) 2012 Humbug, Inc.
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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

if options.forward_class_messages and not options.noshard:
    sys.path.append("/home/humbug/humbug")
    from zephyr.lib.parallel import run_parallel
    print "Starting parallel zephyr class mirroring bot"
    jobs = list("0123456789abcdef")
    def run_job(shard):
        subprocess.call(args + ["--shard=%s" % (shard,)])
        return 0
    for (status, job) in run_parallel(run_job, jobs, threads=16):
        print "A mirroring shard died!"
        pass
    sys.exit(0)

while True:
    print "Starting zephyr mirroring bot"
    try:
        subprocess.call(args)
    except:
        traceback.print_exc()
    time.sleep(1)
