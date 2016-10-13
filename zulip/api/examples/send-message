#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import print_function
import sys
import os
import optparse
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import zulip

usage = """send-message --user=<bot's email address> --api-key=<bot's api key> [options] <recipients>

Sends a test message to the specified recipients.

Example: send-message --user=your-bot@example.com --api-key=a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 --type=stream commits --subject="my subject" --message="test message"
Example: send-message --user=your-bot@example.com --api-key=a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5 user1@example.com user2@example.com

You can omit --user and --api-key arguments if you have a properly set up ~/.zuliprc
"""
parser = optparse.OptionParser(usage=usage)
parser.add_option('--subject', default="test")
parser.add_option('--message', default="test message")
parser.add_option('--type',   default='private')
parser.add_option_group(zulip.generate_option_group(parser))
(options, args) = parser.parse_args()

if len(args) == 0:
    parser.error("You must specify recipients")

client = zulip.init_from_options(options)

message_data = {
    "type": options.type,
    "content": options.message,
    "subject": options.subject,
    "to": args,
}
print(client.send_message(message_data))
