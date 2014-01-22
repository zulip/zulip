#!/usr/bin/python
#
# Copyright (C) 2013 Permabit, Inc.
# Copyright (C) 2013-4 Zulip, Inc.
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

import logging
import threading
import optparse

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
import os, sys, zulip, getpass
import re

def room_to_stream(room):
    return str(room).split("@")[0]

class JabberToZulipBot(ClientXMPP):
    def __init__(self, nick, password, rooms, openfire=False):
        self.nick = nick
        jid = "%s/zulip" % (nick,)
        ClientXMPP.__init__(self, jid, password)
        self.password = password
        self.rooms = rooms
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)
        self.password = password
        self.zulip = None
        self.use_ipv6 = False

        if options.conference_domain is not None:
            # Jabber chatroom support.
            self.register_plugin('xep_0045')

        if openfire:
            # OpenFire Jabber servers use a different SSL protocol version
            import ssl
            self.ssl_version = ssl.PROTOCOL_SSLv3

    def setZulipClient(self, client):
        self.zulip = client

    def session_start(self, event):
        self.get_roster()
        self.send_presence()
        if options.stream_mirror and options.conference_domain is not None:
            for room in self.rooms:
                self.plugin['xep_0045'].joinMUC(room + "@" + options.conference_domain,
                                                self.nick)

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
        if msg["from"] == self.jid or msg['thread'] == u'\u1B80':
            return
        sender = self.jid_to_zulip(msg["from"])
        recipient = self.jid_to_zulip(msg["to"])

        zulip_message = dict(
            sender = sender,
            type = "private",
            to = recipient,
            content = msg["body"],
            )
        ret = self.zulip.send_message(zulip_message)
        if ret.get("status") != "success":
            logging.error(ret)

    def group(self, msg):
        if msg.get_mucnick() == self.nick or msg["thread"] == u'\u1B80':
            return

        subject = msg["subject"]
        if len(subject) == 0:
            subject = "(no topic)"
        stream = room_to_stream(msg.get_mucroom())
        jid = self.nickname_to_jid(msg.get_mucroom(), msg.get_mucnick())
        sender = self.jid_to_zulip(jid)
        zulip_message = dict(
            forged = "yes",
            sender = sender,
            type = "stream",
            subject = subject,
            to = stream,
            content = msg["body"],
            )
        ret = self.zulip.send_message(zulip_message)
        if ret.get("status") != "success":
            logging.error(ret)

    def jid_to_zulip(self, jid):
        return "%s@%s" % (str(jid).split("@")[0], options.zulip_domain)

    def nickname_to_jid(self, room, nick):
        jid = self.plugin['xep_0045'].getJidProperty(room, nick, "jid")
        if (jid is None or jid == ''):
            return re.sub(' ', '', nick) + "@" + options.jabber_domain
        else:
            return jid

class ZulipToJabberBot(zulip.Client):
    def __init__(self, email, api_key):
        zulip.Client.__init__(self, email, api_key, client="jabber_mirror",
                              site=options.zulip_server, verbose=False)
        self.jabber = None
        self.email = email

    def setJabberClient(self, client):
        self.jabber = client

    def process_message(self, event):
        try:
            if event['type'] != 'message':
                return
            message = event["message"]
            if message['sender_email'] != self.email:
                return
            if message['type'] == 'stream':
                self.stream_message(message)
            elif message['type'] == 'private':
                self.private_message(message)
        except:
            logging.exception("Exception forwarding Zulip => Jabber")

    def stream_message(self, msg):
        jabber_recipient = "%s@%s" % (msg['display_recipient'], options.conference_domain)
        outgoing = self.jabber.make_message(
            mto   = jabber_recipient,
            mbody = msg['content'],
            mtype = 'groupchat')
        outgoing['thread'] == u'\u1B80'
        outgoing.send()

    def private_message(self, msg):
        for recipient in msg['display_recipient']:
            if recipient["email"] == self.email:
                continue
            jabber_recipient = recipient['email'].replace(options.zulip_domain, options.jabber_domain)
            outgoing = self.jabber.make_message(
                mto   = jabber_recipient,
                mbody = msg['content'],
                mtype = 'chat')
            outgoing['thread'] == u'\u1B80'
            outgoing.send()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)-8s %(message)s')

    parser = optparse.OptionParser()
    parser.add_option('--openfire',
                      default=False,
                      action='store_true',
                      help="Set if Jabber server is an OpenFire server")
    parser.add_option('--password',
                      default=None,
                      action='store',
                      help="Your Jabber password")
    parser.add_option('--jabber-domain',
                      default=None,
                      action='store',
                      help="Your Jabber server")
    parser.add_option('--stream-mirror',
                      default=False,
                      action='store_true')
    parser.add_option('--no-use-tls',
                      default=False,
                      action='store_true')
    parser.add_option('--zulip-server',
                      default="https://api.zulip.com",
                      action='store',
                      help="Your Zulip API server (only needed for Zulip Enterprise)")
    parser.add_option('--conference-domain',
                      default=None,
                      action='store',
                      help="Your Jabber conference domain (E.g. conference.jabber.example.com)")
    (options, args) = parser.parse_args()

    if len(args) < 2:
        sys.exit("Usage: %s EMAIL ZULIP_APIKEY" % (sys.argv[0],));
    email = args[0]
    ZULIP_API_KEY = args[1]
    if options.password is None:
        options.password = getpass.getpass("Jabber password: ")
    if options.jabber_domain is None:
        sys.exit("Must specify a Jabber server")

    (username, options.zulip_domain) = email.split("@")
    jabber_username = username + '@' + options.jabber_domain

    zulip = ZulipToJabberBot(email=email, api_key=ZULIP_API_KEY);
    rooms = [s['name'] for s in zulip.get_streams()['streams']]
    xmpp = JabberToZulipBot(jabber_username, options.password, rooms,
                            openfire=options.openfire)
    xmpp.connect(use_tls=not options.no_use_tls)
    xmpp.process(block=False)
    xmpp.setZulipClient(zulip)
    zulip.setJabberClient(xmpp)
    try:
        logging.info("Connecting to Zulip.")
        zulip.call_on_each_event(zulip.process_message)
        zulip.session_start()
    except BaseException as e:
        logging.exception("Exception in main loop")
        xmpp.abort()
