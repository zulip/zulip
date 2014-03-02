#!/usr/bin/python
#
# Copyright (C) 2013 Permabit, Inc.
# Copyright (C) 2013--2014 Zulip, Inc.
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# The following is a table showing which kinds of messages are handled by the
# mirror in each mode:
#
#     Message origin/type --> |  Jabber  |   Zulip
#  Mode/sender-,              +-----+----+--------+----
#              V              | MUC | PM | stream | PM
# --------------+-------------+-----+----+--------+----
#               | other sender|     | x  |        |
# personal mode +-------------+-----+----+--------+----
#               | self sender |     | x  |   x    | x
# ------------- +-------------+-----+----+--------+----
#               | other sender|  x  |    |        |
# public mode   +-------------+-----+----+--------+----
#               | self sender |     |    |        |

import logging
import threading
import optparse

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
import os, sys, zulip, getpass
import re

__version__ = "1.1"

def room_to_stream(room):
    return str(room).rpartition("@")[0] + "/xmpp"

def stream_to_room(stream):
    return stream.lower().rpartition("/xmpp")[0]

def jid_to_zulip(jid):
    return "%s@%s" % (str(jid).rpartition("@")[0], options.zulip_domain)

class JabberToZulipBot(ClientXMPP):
    def __init__(self, nick, domain, password, rooms, openfire=False):
        self.nick = nick
        jid = "%s@%s/jabber_mirror" % (nick, domain)
        ClientXMPP.__init__(self, jid, password)
        self.password = password
        self.rooms = set()
        self.rooms_to_join = rooms
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.password = password
        self.zulip = None
        self.use_ipv6 = False

        self.register_plugin('xep_0045') # Jabber chatrooms
        self.register_plugin('xep_0199') # XMPP Ping

        if openfire:
            # OpenFire Jabber servers use a different SSL protocol version
            import ssl
            self.ssl_version = ssl.PROTOCOL_SSLv3

    def set_zulip_client(self, client):
        self.zulip = client

    def session_start(self, event):
        self.get_roster()
        self.send_presence()
        for room in self.rooms_to_join:
            self.join_muc(room)

    def join_muc(self, room):
        if room in self.rooms:
            return
        logging.debug("Joining " + room)
        self.rooms.add(room)
        muc_jid = room + "@" + options.conference_domain
        self.plugin['xep_0045'].joinMUC(muc_jid, self.nick)

    def leave_muc(self, room):
        if room not in self.rooms:
            return
        logging.debug("Leaving " + room)
        self.rooms.remove(room)
        muc_jid = room + "@" + options.conference_domain
        self.plugin['xep_0045'].leaveMUC(muc_jid, self.nick)

    def message(self, msg):
        try:
            if msg["type"] == "groupchat":
                return self.group(msg)
            elif msg["type"] == "chat":
                return self.private(msg)
            else:
                logging.warning("Got unexpected message type")
                logging.warning(msg)
        except Exception:
            logging.exception("Error forwarding Jabber => Zulip")

    def private(self, msg):
        if options.mode == 'public' or msg['thread'] == u'\u1B80':
            return
        sender = jid_to_zulip(msg["from"])
        recipient = jid_to_zulip(msg["to"])

        zulip_message = dict(
            sender = sender,
            type = "private",
            to = recipient,
            content = msg["body"],
            )
        ret = self.zulip.client.send_message(zulip_message)
        if ret.get("status") != "success":
            logging.error(ret)

    def group(self, msg):
        if options.mode == 'personal' or msg["thread"] == u'\u1B80':
            return

        subject = msg["subject"]
        if len(subject) == 0:
            subject = "(no topic)"
        stream = room_to_stream(msg.get_mucroom())
        jid = self.nickname_to_jid(msg.get_mucroom(), msg.get_mucnick())
        sender = jid_to_zulip(jid)
        zulip_message = dict(
            forged = "yes",
            sender = sender,
            type = "stream",
            subject = subject,
            to = stream,
            content = msg["body"],
            )
        ret = self.zulip.client.send_message(zulip_message)
        if ret.get("status") != "success":
            logging.error(ret)

    def nickname_to_jid(self, room, nick):
        jid = self.plugin['xep_0045'].getJidProperty(room, nick, "jid")
        if (jid is None or jid == ''):
            return nick.replace(' ', '') + "@" + options.jabber_domain
        else:
            return jid

class ZulipToJabberBot(object):
    def __init__(self, zulip_client):
        self.client = zulip_client
        self.jabber = None

    def set_jabber_client(self, client):
        self.jabber = client

    def process_event(self, event):
        if event['type'] == 'message':
            message = event["message"]
            if message['sender_email'] != self.client.email:
                return

            try:
                if message['type'] == 'stream':
                    self.stream_message(message)
                elif message['type'] == 'private':
                    self.private_message(message)
            except:
                logging.exception("Exception forwarding Zulip => Jabber")
        elif event['type'] == 'subscription':
            self.process_subscription(event)
        elif event['type'] == 'stream':
            self.process_stream(event)

    def stream_message(self, msg):
        stream = msg['display_recipient']
        if not stream.endswith("/xmpp"):
            return

        room = stream_to_room(stream)
        jabber_recipient = "%s@%s" % (room, options.conference_domain)
        outgoing = self.jabber.make_message(
            mto   = jabber_recipient,
            mbody = msg['content'],
            mtype = 'groupchat')
        outgoing['thread'] = u'\u1B80'
        outgoing.send()

    def private_message(self, msg):
        for recipient in msg['display_recipient']:
            if recipient["email"] == self.client.email:
                continue
            recip_email = recipient['email']
            username = recip_email[:recip_email.rfind(options.zulip_domain)]
            jabber_recipient = username + options.jabber_domain
            outgoing = self.jabber.make_message(
                mto   = jabber_recipient,
                mbody = msg['content'],
                mtype = 'chat')
            outgoing['thread'] = u'\u1B80'
            outgoing.send()

    def process_subscription(self, event):
        if event['op'] == 'add':
            streams = [s['name'].lower() for s in event['subscriptions']]
            streams = [s for s in streams if s.endswith("/xmpp")]
            for stream in streams:
                self.jabber.join_muc(stream_to_room(stream))
        if event['op'] == 'remove':
            streams = [s['name'].lower() for s in event['subscriptions']]
            streams = [s for s in streams if s.endswith("/xmpp")]
            for stream in streams:
                self.jabber.leave_muc(stream_to_room(stream))

    def process_stream(self, event):
        if event['op'] == 'occupy':
            streams = [s['name'].lower() for s in event['streams']]
            streams = [s for s in streams if s.endswith("/xmpp")]
            for stream in streams:
                self.jabber.join_muc(stream_to_room(stream))
        if event['op'] == 'vacate':
            streams = [s['name'].lower() for s in event['streams']]
            streams = [s for s in streams if s.endswith("/xmpp")]
            for stream in streams:
                self.jabber.leave_muc(stream_to_room(stream))

def get_rooms(zulip):
    if options.mode == 'public':
        stream_infos = zulip.client.get_streams()['streams']
    else:
        stream_infos = zulip.client.list_subscriptions()['subscriptions']

    rooms = []
    for stream_info in stream_infos:
            stream = stream_info['name']
            if stream.endswith("/xmpp"):
                rooms.append(stream_to_room(stream))
    return rooms

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('--mode',
                      default="personal",
                      action='store',
                      help= \
'''Which mode to run in.  Valid options are "personal" and "public".  In
"personal" mode, the mirror uses an individual users' credentials and mirrors
all messages they send on Zulip to Jabber and all private Jabber messages to
Zulip.  In "public" mode, the mirror uses the credentials for a dedicated mirror
user and mirrors messages sent to Jabber rooms to Zulip.'''.replace("\n", " "))
    parser.add_option('-d', '--debug',
                      help='set logging to DEBUG',
                      action='store_const',
                      dest='log_level',
                      const=logging.DEBUG,
                      default=logging.INFO)

    jabber_group = optparse.OptionGroup(parser, "Jabber configuration")
    jabber_group.add_option('--openfire',
                            default=False,
                            action='store_true',
                            help="Set if Jabber server is an OpenFire server")
    jabber_group.add_option('--jabber-username',
                            default=None,
                            action='store',
                            help="Your Jabber username")
    jabber_group.add_option('--jabber-password',
                            default=None,
                            action='store',
                            help="Your Jabber password")
    jabber_group.add_option('--jabber-domain',
                            default=None,
                            action='store',
                            help="Your Jabber server")
    jabber_group.add_option('--no-use-tls',
                            default=False,
                            action='store_true')
    jabber_group.add_option('--conference-domain',
                            default=None,
                            action='store',
                            help="Your Jabber conference domain (E.g. conference.jabber.example.com).  "
                            + "Only required when running in \"public\" mode.")

    parser.add_option_group(jabber_group)
    parser.add_option_group(zulip.generate_option_group(parser, "zulip-"))
    (options, args) = parser.parse_args()

    logging.basicConfig(level=options.log_level,
                        format='%(levelname)-8s %(message)s')

    if options.mode not in ('public', 'personal'):
        sys.exit("Bad value for --mode: must be one of 'public' or 'personal'")

    if options.mode == 'public' and options.conference_domain is None:
        sys.exit("--conference-domain is required when running in 'public' mode")

    if options.jabber_password is None:
        options.jabber_password = getpass.getpass("Jabber password: ")
    if options.jabber_domain is None:
        sys.exit("Must specify a Jabber server")


    # This won't work for open realms
    options.zulip_domain = options.zulip_email.partition('@')[-1]

    zulip = ZulipToJabberBot(zulip.init_from_options(options, "JabberMirror/" + __version__))
    xmpp = JabberToZulipBot(options.jabber_username, options.jabber_domain,
                            options.jabber_password, get_rooms(zulip),
                            openfire=options.openfire)

    if not xmpp.connect(use_tls=not options.no_use_tls):
        sys.exit("Unable to connect to Jabber server")

    xmpp.set_zulip_client(zulip)
    zulip.set_jabber_client(xmpp)

    xmpp.process(block=False)
    if options.mode == 'public':
        event_types = ['stream']
    else:
        event_types = ['message', 'subscription']

    try:
        logging.info("Connecting to Zulip.")
        zulip.client.call_on_each_event(zulip.process_event,
                                        event_types=event_types)
    except BaseException as e:
        logging.exception("Exception in main loop")
        xmpp.abort()
