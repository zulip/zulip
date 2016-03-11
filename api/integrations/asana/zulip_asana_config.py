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


### REQUIRED CONFIGURATION ###

# Change these values to your Asana credentials.
ASANA_API_KEY = "0123456789abcdef0123456789abcdef"

# Change these values to the credentials for your Asana bot.
ZULIP_USER = "asana-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"

# The Zulip stream that will receive Asana task updates.
ZULIP_STREAM_NAME = "asana"


### OPTIONAL CONFIGURATION ###

# Set to None for logging to stdout when testing, and to a file for
# logging in production.
#LOG_FILE = "/var/tmp/zulip_asana.log"
LOG_FILE = None

# This file is used to resume this mirror in case the script shuts down.
# It is required and needs to be writeable.
RESUME_FILE = "/var/tmp/zulip_asana.state"

# When initially started, how many hours of messages to include.
ASANA_INITIAL_HISTORY_HOURS = 1

# Set this to your Zulip API server URI
ZULIP_SITE = "https://api.zulip.com"

# If properly installed, the Zulip API should be in your import
# path, but if not, set a custom path below
ZULIP_API_PATH = None
