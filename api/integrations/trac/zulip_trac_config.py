# -*- coding: utf-8 -*-
#
# Copyright © 2012 Zulip, Inc.
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

# See zulip_trac.py for installation and configuration instructions

# Change these constants to configure the plugin:
ZULIP_USER = "trac-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
STREAM_FOR_NOTIFICATIONS = "trac"
TRAC_BASE_TICKET_URL = "https://trac.example.com/ticket"

# Most people find that having every change in Trac result in a
# notification is too noisy -- in particular, when someone goes
# through recategorizing a bunch of tickets, that can often be noisy
# and annoying.  We solve this issue by only sending a notification
# for changes to the fields listed below.
#
# TRAC_NOTIFY_FIELDS lets you specify which fields will trigger a
# Zulip notification in response to a trac update; you should change
# this list to match your team's workflow.  The complete list of
# possible fields is:
#
# (priority, milestone, cc, owner, keywords, component, severity,
#  type, versions, description, resolution, summary, comment)
TRAC_NOTIFY_FIELDS = ["description", "summary", "resolution", "comment", "owner"]

## If properly installed, the Zulip API should be in your import
## path, but if not, set a custom path below
ZULIP_API_PATH = None

# Set this to your Zulip API server URI
ZULIP_SITE = "https://api.zulip.com"
