#!/usr/bin/python
#
# Humbug trac plugin -- sends humbugs when tickets change.
#
# Install by placing in the plugins/ subdirectory and then adding
# "humbug_trac" to the [components] section of the conf/trac.ini file,
# like so:
#
# [components]
# humbug_trac = enabled
#
# You may then need to restart trac (or restart Apache) for the bot
# (or changes to the bot) to actually be loaded by trac.
#
# Our install is trac.humbughq.com:/home/humbug/trac/

from trac.core import Component, implements
from trac.ticket import ITicketChangeListener
import sys

# This script lives on one machine, so an absolute path is fine.
sys.path.append("/home/humbug/humbug/api")
import humbug
client = humbug.Client(
    email="humbug+trac@humbughq.com",
    site="https://staging.humbughq.com",
    api_key="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

def markdown_ticket_url(ticket, heading="ticket"):
    return "[%s #%s](https://trac.humbughq.com/ticket/%s)" % (heading, ticket.id, ticket.id)

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
            "to": "trac",
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
