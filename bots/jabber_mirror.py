#!/usr/bin/env python
# Copyright (C) 2014 Zulip, Inc.
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

from __future__ import print_function
import sys
import subprocess
import os
import traceback
import signal
from types import FrameType
from typing import Any
from zulip import RandomExponentialBackoff

def die(signal, frame):
    # type: (int, FrameType) -> None
    """We actually want to exit, so run os._exit (so as not to be caught and restarted)"""
    os._exit(1)

signal.signal(signal.SIGINT, die)

args = [os.path.join(os.path.dirname(sys.argv[0]), "jabber_mirror_backend.py")]
args.extend(sys.argv[1:])

backoff = RandomExponentialBackoff(timeout_success_equivalent=300)
while backoff.keep_going():
    print("Starting Jabber mirroring bot")
    try:
        ret = subprocess.call(args)
    except Exception:
        traceback.print_exc()
    else:
        if ret == 2:
            # Don't try again on initial configuration errors
            sys.exit(ret)

    backoff.fail()

print("")
print("")
print("ERROR: The Jabber mirroring bot is unable to continue mirroring Jabber.")
print("Please contact zulip-devel@googlegroups.com if you need assistance.")
print("")
sys.exit(1)
