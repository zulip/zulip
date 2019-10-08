# Zulip in a Terminal

At present, there are a few alpha-quality implementations of a terminal
client for Zulip:

* [Zulip Terminal](https://github.com/zulip/zulip-terminal) provides a
terminal interface for Zulip using [Urwid](https://urwid.org). It is
written in python and is being very actively developed; feedback and
bug reports are very welcome!

* [Barnowl](https://github.com/aglasgall/barnowl/tree/zulip) is a
multi-protocol terminal client for various chat systems, written in
Perl.  [Barnowl itself](https://barnowl.mit.edu/) is very mature
software, and the Zulip integration has been used for a few years, but
it isn't integrated into the mainline branch and needs work on
documentation.

* [Snipe](https://github.com/kcr/snipe) is relatively new
multi-protocol client for various chat systems, built on Python 3 and
asyncio.

Zulip's web and mobile apps use the same REST API that we publish in
our [API documentation](/api), as do all three of these terminal
clients, so it should require only client-side work to build a
high quality terminal-based app for Zulip.
