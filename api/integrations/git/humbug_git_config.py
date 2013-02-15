#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2013 Humbug, Inc.
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


# Change these values to configure authentication for the plugin
HUMBUG_USER = "git@example.com"
HUMBUG_API_KEY = "0123456789abcdef0123456789abcdef"

# commit_notice_destination() lets you customize where commit notices
# are sent to with the full power of a Python function.
#
# It takes the following arguments:
# * repo   = the name of the git repository
# * branch = the name of the branch that was pushed to
# * commit = the commit id
#
# Returns a dictionary encoding the stream and subject to send the
# notification to (or None to send no notification).
#
# The default code below will send every commit pushed to "master" to
# * stream "commits"
# * subject "deploy => master" (using a pretty unicode right arrow)
# And similarly for branch "test-post-receive" (for use when testing).
def commit_notice_destination(repo, branch, commit):
    if branch in ["master", "test-post-receive"]:
        return dict(stream  = "commits",
                    subject = u"deploy \u21D2 %s" % (branch,))

    # Return None for cases where you don't want a notice sent
    return None

## If properly installed, the Humbug API should be in your import
## path, but if not, set a custom path below
HUMBUG_API_PATH = None

# This should not need to change unless you have a custom Humbug subdomain.
HUMBUG_SITE = "https://humbughq.com"
