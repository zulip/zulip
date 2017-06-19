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
created, files have been transferred, and the changelist committed to the depot
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
from typing import Any, Dict, Optional, Text
import zulip_perforce_config as config

if config.ZULIP_API_PATH is not None:
    sys.path.append(config.ZULIP_API_PATH)

import zulip
client = zulip.Client(
    email=config.ZULIP_USER,
    site=config.ZULIP_SITE,
    api_key=config.ZULIP_API_KEY,
    client="ZulipPerforce/" + __version__)  # type: zulip.Client

try:
    changelist = int(sys.argv[1])  # type: int
    changeroot = sys.argv[2]  # type: str
except IndexError:
    print("Wrong number of arguments.\n\n", end=' ', file=sys.stderr)
    print(__doc__, file=sys.stderr)
    sys.exit(-1)
except ValueError:
    print("First argument must be an integer.\n\n", end=' ', file=sys.stderr)
    print(__doc__, file=sys.stderr)
    sys.exit(-1)

metadata = git_p4.p4_describe(changelist)  # type: Dict[str, str]

destination = config.commit_notice_destination(changeroot, changelist)  # type: Optional[Dict[str, str]]

if destination is None:
    # Don't forward the notice anywhere
    sys.exit(0)

ignore_missing_stream = None
if hasattr(config, "ZULIP_IGNORE_MISSING_STREAM"):
    ignore_missing_stream = config.ZULIP_IGNORE_MISSING_STREAM

if ignore_missing_stream:
    # Check if the destination stream exists yet
    stream_state = client.get_stream_id(destination["stream"])
    if stream_state["result"] == "error":
        # Silently discard the message
        sys.exit(0)

change = metadata["change"]
p4web = None
if hasattr(config, "P4_WEB"):
    p4web = config.P4_WEB

if p4web is not None:
    # linkify the change number
    change = '[{change}]({p4web}/{change}?ac=10)'.format(p4web=p4web, change=change)

message = """**{user}** committed revision @{change} to `{path}`.

```quote
{desc}
```
""".format(
    user=metadata["user"],
    change=change,
    path=changeroot,
    desc=metadata["desc"])  # type: str

message_data = {
    "type": "stream",
    "to": destination["stream"],
    "subject": destination["subject"],
    "content": message,
}  # type: Dict[str, Any]
client.send_message(message_data)
