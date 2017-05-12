#!/usr/bin/env python
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
from typing import Dict, List, Set

import logging
import threading
import optparse

from sleekxmpp import ClientXMPP, InvalidJID, JID
from sleekxmpp.stanza import Message as JabberMessage
from sleekxmpp.exceptions import IqError, IqTimeout
from six.moves.configparser import SafeConfigParser
import getpass
import os
import sys
import zulip
from zulip import Client
import re
from typing import Any, Callable

__version__ = "1.1"

def room_to_stream(room):
    # type: (str) -> str
    return room + "/xmpp"

def stream_to_room(stream):
    # type: (str) -> str
    return stream.lower().rpartition("/xmpp")[0]

def jid_to_zulip(jid):
    # type: (JID) -> str
    suffix = ''
    if not jid.username.endswith("-bot"):
        suffix = options.zulip_email_suffix
    return "%s%s@%s" % (jid.username, suffix, options.zulip_domain)

def zulip_to_jid(email, jabber_domain):
    # type: (str, str) -> JID
    jid = JID(email, domain=jabber_domain)
    if (options.zulip_email_suffix and
        options.zulip_email_suffix in jid.username and
            not jid.username.endswith("-bot")):
        jid.username = jid.username.rpartition(options.zulip_email_suffix)[0]
    return jid

class JabberToZulipBot(ClientXMPP):
    def __init__(self, jid, password, rooms):
        # type: (JID, str, List[str]) -> None
        if jid.resource:
            self.nick = jid.resource
        else:
            self.nick = jid.username
            jid.resource = "zulip"
        ClientXMPP.__init__(self, jid, password)
        self.rooms = set()  # type: Set[str]
        self.rooms_to_join = rooms
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.zulip = None  # type: Client
        self.use_ipv6 = False

        self.register_plugin('xep_0045')  # Jabber chatrooms
        self.register_plugin('xep_0199')  # XMPP Ping

    def set_zulip_client(self, zulipToJabberClient):
        # type: (ZulipToJabberBot) -> None
        self.zulipToJabber = zulipToJabberClient

    def session_start(self, event):
        # type: (Dict[str, Any]) -> None
        self.get_roster()
        self.send_presence()
        for room in self.rooms_to_join:
            self.join_muc(room)

    def join_muc(self, room):
        # type: (str) -> None
        if room in self.rooms:
            return
        logging.debug("Joining " + room)
        self.rooms.add(room)
        muc_jid = JID(local=room, domain=options.conference_domain)
        xep0045 = self.plugin['xep_0045']
        try:
            xep0045.joinMUC(muc_jid, self.nick, wait=True)
        except InvalidJID:
            logging.error("Could not join room: " + str(muc_jid))
            return

        # Configure the room.  Really, we should only do this if the room is
        # newly created.
        form = None
        try:
            form = xep0045.getRoomConfig(muc_jid)
        except ValueError:
            pass
        if form:
            xep0045.configureRoom(muc_jid, form)
        else:
            logging.error("Could not configure room: " + str(muc_jid))

    def leave_muc(self, room):
        # type: (str) -> None
        if room not in self.rooms:
            return
        logging.debug("Leaving " + room)
        self.rooms.remove(room)
        muc_jid = JID(local=room, domain=options.conference_domain)
        self.plugin['xep_0045'].leaveMUC(muc_jid, self.nick)

    def message(self, msg):
        # type: (JabberMessage) -> Any
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
        # type: (JabberMessage) -> None
        if options.mode == 'public' or msg['thread'] == u'\u1FFFE':
            return
        sender = jid_to_zulip(msg["from"])
        recipient = jid_to_zulip(msg["to"])

        zulip_message = dict(
            sender = sender,
            type = "private",
            to = recipient,
            content = msg["body"],
        )
        ret = self.zulipToJabber.client.send_message(zulip_message)
        if ret.get("result") != "success":
            logging.error(str(ret))

    def group(self, msg):
        # type: (JabberMessage) -> None
        if options.mode == 'personal' or msg["thread"] == u'\u1FFFE':
            return

        subject = msg["subject"]
        if len(subject) == 0:
            subject = "(no topic)"
        stream = room_to_stream(msg['from'].local)
        sender_nick = msg.get_mucnick()
        if not sender_nick:
            # Messages from the room itself have no nickname.  We should not try
            # to mirror these
            return
        jid = self.nickname_to_jid(msg.get_mucroom(), sender_nick)
        sender = jid_to_zulip(jid)
        zulip_message = dict(
            forged = "yes",
            sender = sender,
            type = "stream",
            subject = subject,
            to = stream,
            content = msg["body"],
        )
        ret = self.zulipToJabber.client.send_message(zulip_message)
        if ret.get("result") != "success":
            logging.error(str(ret))

    def nickname_to_jid(self, room, nick):
        # type: (str, str) -> JID
        jid = self.plugin['xep_0045'].getJidProperty(room, nick, "jid")
        if (jid is None or jid == ''):
            return JID(local=nick.replace(' ', ''), domain=self.boundjid.domain)
        else:
            return jid

class ZulipToJabberBot(object):
    def __init__(self, zulip_client):
        # type: (Client) -> None
        self.client = zulip_client
        self.jabber = None  # type: JabberToZulipBot

    def set_jabber_client(self, client):
        # type: (JabberToZulipBot) -> None
        self.jabber = client

    def process_event(self, event):
        # type: (Dict[str, Any]) -> None
        if event['type'] == 'message':
            message = event["message"]
            if message['sender_email'] != self.client.email:
                return

            try:
                if message['type'] == 'stream':
                    self.stream_message(message)
                elif message['type'] == 'private':
                    self.private_message(message)
            except Exception:
                logging.exception("Exception forwarding Zulip => Jabber")
        elif event['type'] == 'subscription':
            self.process_subscription(event)
        elif event['type'] == 'stream':
            self.process_stream(event)

    def stream_message(self, msg):
        # type: (Dict[str, str]) -> None
        stream = msg['display_recipient']
        if not stream.endswith("/xmpp"):
            return

        room = stream_to_room(stream)
        jabber_recipient = JID(local=room, domain=options.conference_domain)
        outgoing = self.jabber.make_message(
            mto   = jabber_recipient,
            mbody = msg['content'],
            mtype = 'groupchat')
        outgoing['thread'] = u'\u1FFFE'
        outgoing.send()

    def private_message(self, msg):
        # type: (Dict[str, Any]) -> None
        for recipient in msg['display_recipient']:
            if recipient["email"] == self.client.email:
                continue
            if not recipient["is_mirror_dummy"]:
                continue
            recip_email = recipient['email']
            jabber_recipient = zulip_to_jid(recip_email, self.jabber.boundjid.domain)
            outgoing = self.jabber.make_message(
                mto   = jabber_recipient,
                mbody = msg['content'],
                mtype = 'chat')
            outgoing['thread'] = u'\u1FFFE'
            outgoing.send()

    def process_subscription(self, event):
        # type: (Dict[str, Any]) -> None
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
        # type: (Dict[str, Any]) -> None
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

def get_rooms(zulipToJabber):
    # type: (ZulipToJabberBot) -> List[str]
    def get_stream_infos(key, method):
        # type: (str, Callable) -> Any
        ret = method()
        if ret.get("result") != "success":
            logging.error(ret)
            sys.exit("Could not get initial list of Zulip %s" % (key,))
        return ret[key]

    if options.mode == 'public':
        stream_infos = get_stream_infos("streams", zulipToJabber.client.get_streams)
    else:
        stream_infos = get_stream_infos("subscriptions", zulipToJabber.client.list_subscriptions)

    rooms = []  # type: List[str]
    for stream_info in stream_infos:
            stream = stream_info['name']
            if stream.endswith("/xmpp"):
                rooms.append(stream_to_room(stream))
    return rooms

def config_error(msg):
    # type: (str) -> None
    sys.stderr.write("%s\n" % (msg,))
    sys.exit(2)

if __name__ == '__main__':
    parser = optparse.OptionParser(
        epilog='''Most general and Jabber configuration options may also be specified in the
zulip configuration file under the jabber_mirror section (exceptions are noted
in their help sections).  Keys have the same name as options with hyphens
replaced with underscores.  Zulip configuration options go in the api section,
as normal.'''.replace("\n", " ")
    )
    parser.add_option(
        '--mode',
        default=None,
        action='store',
        help='''Which mode to run in.  Valid options are "personal" and "public".  In
"personal" mode, the mirror uses an individual users' credentials and mirrors
all messages they send on Zulip to Jabber and all private Jabber messages to
Zulip.  In "public" mode, the mirror uses the credentials for a dedicated mirror
user and mirrors messages sent to Jabber rooms to Zulip.  Defaults to
"personal"'''.replace("\n", " "))
    parser.add_option(
        '--zulip-email-suffix',
        default=None,
        action='store',
        help='''Add the specified suffix to the local part of email addresses constructed
from JIDs and nicks before sending requests to the Zulip server, and remove the
suffix before sending requests to the Jabber server.  For example, specifying
"+foo" will cause messages that are sent to the "bar" room by nickname "qux" to
be mirrored to the "bar/xmpp" stream in Zulip by user "qux+foo@example.com". This
option does not affect login credentials.'''.replace("\n", " "))
    parser.add_option('-d', '--debug',
                      help='set logging to DEBUG.  Can not be set via config file.',
                      action='store_const',
                      dest='log_level',
                      const=logging.DEBUG,
                      default=logging.INFO)

    jabber_group = optparse.OptionGroup(parser, "Jabber configuration")
    jabber_group.add_option(
        '--jid',
        default=None,
        action='store',
        help="Your Jabber JID.  If a resource is specified, "
             "it will be used as the nickname when joining MUCs.  "
             "Specifying the nickname is mostly useful if you want "
             "to run the public mirror from a regular user instead of "
             "from a dedicated account.")
    jabber_group.add_option('--jabber-password',
                            default=None,
                            action='store',
                            help="Your Jabber password")
    jabber_group.add_option('--conference-domain',
                            default=None,
                            action='store',
                            help="Your Jabber conference domain (E.g. conference.jabber.example.com).  "
                                 "If not specifed, \"conference.\" will be prepended to your JID's domain.")
    jabber_group.add_option('--no-use-tls',
                            default=None,
                            action='store_true')
    jabber_group.add_option('--jabber-server-address',
                            default=None,
                            action='store',
                            help="The hostname of your Jabber server. This is only needed if "
                            "your server is missing SRV records")
    jabber_group.add_option('--jabber-server-port',
                            default='5222',
                            action='store',
                            help="The port of your Jabber server. This is only needed if "
                            "your server is missing SRV records")

    parser.add_option_group(jabber_group)
    parser.add_option_group(zulip.generate_option_group(parser, "zulip-"))
    (options, args) = parser.parse_args()

    logging.basicConfig(level=options.log_level,
                        format='%(levelname)-8s %(message)s')

    if options.zulip_config_file is None:
        config_file = zulip.get_default_config_filename()
    else:
        config_file = options.zulip_config_file

    config = SafeConfigParser()
    try:
        with open(config_file, 'r') as f:
            config.readfp(f, config_file)
    except IOError:
        pass
    for option in ("jid", "jabber_password", "conference_domain", "mode", "zulip_email_suffix",
                   "jabber_server_address", "jabber_server_port"):
        if (getattr(options, option) is None and
                config.has_option("jabber_mirror", option)):
            setattr(options, option, config.get("jabber_mirror", option))

    for option in ("no_use_tls",):
        if getattr(options, option) is None:
            if config.has_option("jabber_mirror", option):
                setattr(options, option, config.getboolean("jabber_mirror", option))
            else:
                setattr(options, option, False)

    if options.mode is None:
        options.mode = "personal"

    if options.zulip_email_suffix is None:
        options.zulip_email_suffix = ''

    if options.mode not in ('public', 'personal'):
        config_error("Bad value for --mode: must be one of 'public' or 'personal'")

    if None in (options.jid, options.jabber_password):
        config_error("You must specify your Jabber JID and Jabber password either "
                     "in the Zulip configuration file or on the commandline")

    zulipToJabber = ZulipToJabberBot(zulip.init_from_options(options, "JabberMirror/" + __version__))
    # This won't work for open realms that don't have a consistent domain
    options.zulip_domain = zulipToJabber.client.email.partition('@')[-1]

    try:
        jid = JID(options.jid)
    except InvalidJID as e:
        config_error("Bad JID: %s: %s" % (options.jid, e.message))

    if options.conference_domain is None:
        options.conference_domain = "conference.%s" % (jid.domain,)

    xmpp = JabberToZulipBot(jid, options.jabber_password, get_rooms(zulipToJabber))

    address = None
    if options.jabber_server_address:
        address = (options.jabber_server_address, options.jabber_server_port)

    if not xmpp.connect(use_tls=not options.no_use_tls, address=address):
        sys.exit("Unable to connect to Jabber server")

    xmpp.set_zulip_client(zulipToJabber)
    zulipToJabber.set_jabber_client(xmpp)

    xmpp.process(block=False)
    if options.mode == 'public':
        event_types = ['stream']
    else:
        event_types = ['message', 'subscription']

    try:
        logging.info("Connecting to Zulip.")
        zulipToJabber.client.call_on_each_event(zulipToJabber.process_event,
                                                event_types=event_types)
    except BaseException as e:
        logging.exception("Exception in main loop")
        xmpp.abort()
        sys.exit(1)
