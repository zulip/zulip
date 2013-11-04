#! /usr/bin/env python
#
# EXPERIMENTAL
# IRC <=> Zulip mirroring bot
#
# Setup: First, you need to install python-irc version 8.5.3
# (https://bitbucket.org/jaraco/irc)

import irc.bot
import irc.strings
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr
import zulip
import optparse

def zulip_sender(sender_string):
    nick = sender_string.split("!")[0]
    return nick + "@irc.zulip.com"

class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname().replace("_zulip", "__zulip"))

    def on_welcome(self, c, e):
        c.join(self.channel)
        def forward_to_irc(msg):
            if msg["type"] == "stream":
                send = lambda x: c.privmsg(msg["display_recipient"], x)
            else:
                recipients = [u["short_name"] for u in msg["display_recipient"] if
                              u["email"] != msg["sender_email"]]
                if len(recipients) == 1:
                    send = lambda x: c.privmsg(recipients[0], x)
                else:
                    send = lambda x: c.privmsg_many(recipients, x)
            for line in msg["content"].split("\n"):
                send(line)

        ## Forwarding from Zulip => IRC is disabled; uncomment the next
        ## line to make this bot forward in that direction instead.
        #
        # zulip_client.call_on_each_message(forward_to_irc)

    def on_privmsg(self, c, e):
        content = e.arguments[0]
        sender = zulip_sender(e.source)
        if sender.endswith("_zulip@irc.zulip.com"):
            return

        # Forward the PM to Zulip
        print zulip_client.send_message({
                "sender": sender,
                "type": "private",
                "to": "tabbott@zulip.com",
                "content": content,
                })

    def on_pubmsg(self, c, e):
        content = e.arguments[0]
        stream = e.target
        sender = zulip_sender(e.source)
        if sender.endswith("_zulip@irc.zulip.com"):
            return

        # Forward the stream message to Zulip
        print zulip_client.send_message({
                "forged": "yes",
                "sender": sender,
                "type": "stream",
                "to": stream,
                "subject": "IRC",
                "content": content,
                })

    def on_dccmsg(self, c, e):
        c.privmsg("You said: " + e.arguments[0])

    def on_dccchat(self, c, e):
        if len(e.arguments) != 2:
            return
        args = e.arguments[1].split()
        if len(args) == 4:
            try:
                address = ip_numstr_to_quad(args[2])
                port = int(args[3])
            except ValueError:
                return
            self.dcc_connect(address, port)

usage = """python irc-mirror.py --server=IRC_SERVER --channel=<CHANNEL> --nick-prefix=<NICK> [optional args]

Example:

python irc-mirror.py --irc-server=127.0.0.1 --channel='#test' --nick-prefix=tabbott
  --site=https://staging.zulip.com --user=irc-bot@zulip.com
  --api-key=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Note that "_zulip" will be automatically appended to the IRC nick provided

Also note that at present you need to edit this code to do the Zulip => IRC side

"""


if __name__ == "__main__":
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--irc-server', default=None)
    parser.add_option('--port', default=6667)
    parser.add_option('--nick-prefix', default=None)
    parser.add_option('--channel', default=None)
    parser.add_option_group(zulip.generate_option_group(parser))
    (options, args) = parser.parse_args()

    if options.irc_server is None or options.nick_prefix is None or options.channel is None:
        parser.error("Missing required argument")

    # Setting the client to irc_mirror is critical for this to work
    options.client = "irc_mirror"
    zulip_client = zulip.init_from_options(options)

    nickname = options.nick_prefix + "_zulip"
    bot = IRCBot(options.channel, nickname, options.irc_server, options.port)
    bot.start()
