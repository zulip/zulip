#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright © 2012 Humbug, Inc.
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


# Humbug trac plugin -- sends humbugs when tickets change.
#
# Install by copying this file to the trac plugins/ subdirectory,
# customizing the constants below this comment, and then adding
# "humbug_trac" to the [components] section of the conf/trac.ini
# file, like so:
#
# [components]
# humbug_trac = enabled
#
# You may then need to restart trac (or restart Apache) for the bot
# (or changes to the bot) to actually be loaded by trac.

# Change these constants:
HUMBUG_USER = "trac-notifications@example.com"
HUMBUG_API_KEY = "0123456789abcdef0123456789abcdef"
STREAM_FOR_NOTIFICATIONS = "trac"
TRAC_BASE_TICKET_URL = "https://trac.example.com/ticket"

# This should not need to change unless you have a custom Humbug subdomain.
HUMBUG_SITE = "https://humbughq.com"
## If properly installed, the Humbug API should be in your import
## path, but if not, set a custom path below
HUMBUG_API_PATH = None

from trac.core import Component, implements
from trac.ticket import ITicketChangeListener
import sys

if HUMBUG_API_PATH is not None:
    sys.path.append(HUMBUG_API_PATH)

import humbug
client = humbug.Client(
    email=HUMBUG_USER,
    site=HUMBUG_SITE,
    api_key=HUMBUG_API_KEY)

def markdown_ticket_url(ticket, heading="ticket"):
    return "[%s #%s](%s/%s)" % (heading, ticket.id, TRAC_BASE_TICKET_URL, ticket.id)

def markdown_block(desc):
    return "\n\n>" + "\n> ".join(desc.split("\n")) + "\n"

def truncate(string, length):
    if len(string) <= length:
        return string
    return string[:length - 3] + "..."

def trac_subject(ticket):
    return truncate("#%s: %s" % (ticket.id, ticket.values.get("summary")), 60)

def send_update(ticket, content):
    client.send_message({
            "type": "stream",
            "to": STREAM_FOR_NOTIFICATIONS,
            "content": content,
            "subject": trac_subject(ticket)
            })

class HumbugPlugin(Component):
    implements(ITicketChangeListener)

    def ticket_created(self, ticket):
        """Called when a ticket is created."""
        content = "%s created %s in component **%s**, priority **%s**:\n" % \
            (ticket.values.get("reporter"), markdown_ticket_url(ticket),
             ticket.values.get("component"), ticket.values.get("priority"))
        if ticket.values.get("description") != "":
            content += "%s" % markdown_block(ticket.values.get("description"))
        send_update(ticket, content)

    def ticket_changed(self, ticket, comment, author, old_values):
        """Called when a ticket is modified.

        `old_values` is a dictionary containing the previous values of the
        fields that have changed.
        """
        if not comment and set(old_values.keys()) <= set(["priority", "milestone",
                                                          "cc", "keywords",
                                                          "component"]):
            # This is probably someone going through trac and updating
            # the priorities; this can result in a lot of messages
            # nobody wants to read, so don't send them without a comment.
            return

        content = "%s updated %s" % (author, markdown_ticket_url(ticket))
        if comment:
            content += ' with comment: %s\n\n' % (markdown_block(comment,))
        else:
            content += ":\n\n"
        field_changes = []
        for key in old_values.keys():
            if key == "description":
                content += '- Changed %s from %s to %s' % (key, markdown_block(old_values.get(key)),
                                                           markdown_block(ticket.values.get(key)))
            elif old_values.get(key) == "":
                field_changes.append('%s: => **%s**' % (key, ticket.values.get(key)))
            elif ticket.values.get(key) == "":
                field_changes.append('%s: **%s** => ""' % (key, old_values.get(key)))
            else:
                field_changes.append('%s: **%s** => **%s**' % (key, old_values.get(key),
                                                               ticket.values.get(key)))
        content += ", ".join(field_changes)

        send_update(ticket, content)

    def ticket_deleted(self, ticket):
        """Called when a ticket is deleted."""
        content = "%s was deleted." % markdown_ticket_url(ticket, heading="Ticket")
        send_update(ticket, content)
