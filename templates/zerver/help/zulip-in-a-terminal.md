# Zulip in a Terminal
Zulip's web and mobile apps use the same API that we publish
in our API documentation, so writing a terminal client for Zulip
that is just as great as the web app is possible.

At present, there are a few alpha-quality implementations of a terminal
client for Zulip:

## [Zulip Terminal](https://github.com/zulip/zulip-terminal)
Zulip Terminal provides a terminal interface for Zulip using
[Urwid](https://urwid.org). It is written in python and is being
actively developed.

## [Barnowl](https://github.com/aglasgall/barnowl/tree/zulip)
Barnowl is a terminal client for Zulip written in Perl.
[Barnowl](https://barnowl.mit.edu/) itself is well-documented,
but the Zulip integration less so.

## [Snipe](https://github.com/kcr/snipe)
Snipe uses python asyncio to provide a terminal
interface for Zulip. It is not very well documented.
