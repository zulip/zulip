#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2014 Zulip, Inc.
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



# Change these values to configure authentication for basecamp account
BASECAMP_ACCOUNT_ID = "12345678"
BASECAMP_USERNAME = "foo@example.com"
BASECAMP_PASSWORD = "p455w0rd"

# This script will mirror this many hours of history on the first run.
# On subsequent runs this value is ignored.
BASECAMP_INITIAL_HISTORY_HOURS = 0

# Change these values to configure Zulip authentication for the plugin
ZULIP_USER = "basecamp-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
ZULIP_STREAM_NAME = "basecamp"

## If properly installed, the Zulip API should be in your import
## path, but if not, set a custom path below
ZULIP_API_PATH = None

# Set this to your Zulip API server URI
ZULIP_SITE = "https://api.zulip.com"

# If you wish to log to a file rather than stdout/stderr,
# please fill this out your desired path
LOG_FILE = None

# This file is used to resume this mirror in case the script shuts down.
# It is required and needs to be writeable.
RESUME_FILE = "/var/tmp/zulip_basecamp.state"
