# -*- coding: utf-8 -*-
#
# Copyright © 2017 Zulip, Inc.
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

# https://github.com/python/mypy/issues/1141
from typing import Dict, Text

# Change these values to configure authentication for the plugin
ZULIP_USER = 'openshift-bot@example.com'
ZULIP_API_KEY = '0123456789abcdef0123456789abcdef'

# deployment_notice_destination() lets you customize where deployment notices
# are sent to with the full power of a Python function.
#
# It takes the following arguments:
# * branch = the name of the branch where the deployed commit was
#            pushed to
#
# Returns a dictionary encoding the stream and subject to send the
# notification to (or None to send no notification).
#
# The default code below will send every commit pushed to "master" to
# * stream "deployments"
# * topic "master"
# And similarly for branch "test-post-receive" (for use when testing).
def deployment_notice_destination(branch):
    # type: (str) -> Dict[str, Text]
    if branch in ['master', 'test-post-receive']:
        return dict(stream  = 'deployments',
                    subject = u'%s' % (branch,))

    # Return None for cases where you don't want a notice sent
    return None

# Modify this function to change how deployments are displayed
#
# It takes the following arguments:
# * app_name  = the name of the app being deployed
# * url       = the FQDN (Fully Qualified Domain Name) where the app
#                can be found
# * branch    = the name of the branch where the deployed commit was
#                pushed to
# * commit_id = hash of the commit that triggered the deployment
# * dep_id    = deployment id
# * dep_time  = deployment timestamp
def format_deployment_message(
        app_name='', url='', branch='', commit_id='', dep_id='', dep_time=''):
    # type: (str, str, str, str, str, str) -> str
    return 'Deployed commit `%s` (%s) in [%s](%s)' % (
        commit_id, branch, app_name, url)

## If properly installed, the Zulip API should be in your import
## path, but if not, set a custom path below
ZULIP_API_PATH = None  # type: str

# Set this to your Zulip server's API URI
ZULIP_SITE = 'https://zulip.example.com'
