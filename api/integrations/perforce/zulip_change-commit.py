#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2012-2014 Zulip, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
'''Zulip notification change-commit hook.

In Perforce, The "change-commit" trigger is fired after a metadata has been
created, files have been transferred, and the changelist comitted to the depot
database.

This specific trigger expects command-line arguments in the form:
  %change% %changeroot%

For example:
  1234 //depot/security/src/

'''
from __future__ import print_function

import os
import sys
import os.path

import git_p4

__version__ = "0.1"

sys.path.insert(0, os.path.dirname(__file__))
import zulip_perforce_config as config

if config.ZULIP_API_PATH is not None:
    sys.path.append(config.ZULIP_API_PATH)

import zulip
client = zulip.Client(
    email=config.ZULIP_USER,
    site=config.ZULIP_SITE,
    api_key=config.ZULIP_API_KEY,
    client="ZulipPerforce/" + __version__)

try:
    changelist = int(sys.argv[1])
    changeroot = sys.argv[2]
except IndexError:
    print("Wrong number of arguments.\n\n", end=' ', file=sys.stderr)
    print(__doc__, file=sys.stderr)
    sys.exit(-1)
except ValueError:
    print("First argument must be an integer.\n\n", end=' ', file=sys.stderr)
    print(__doc__, file=sys.stderr)
    sys.exit(-1)

metadata = git_p4.p4_describe(changelist)

destination = config.commit_notice_destination(changeroot, changelist)
if destination is None:
    # Don't forward the notice anywhere
    sys.exit(0)

message = """**{0}** committed revision @{1} to `{2}`.

> {3}
""".format(metadata["user"], metadata["change"], changeroot, metadata["desc"])

message_data = {
    "type": "stream",
    "to": destination["stream"],
    "subject": destination["subject"],
    "content": message,
}
client.send_message(message_data)
