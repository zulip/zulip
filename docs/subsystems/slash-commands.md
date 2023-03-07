# Slash commands

Slash commands are commands (mainly for power users) to quickly do
some stuff from the compose box. The codebase refers to these as "zcommand"s,
and both these terms are often user interchangeably.

Currently supported slash commands are:

- `/light` and `/dark` to change the UI theme
- `/ping` to ping to server and get back the time for the round
  trip. Mainly for testing.
- `/fluid-width` and `/fixed-width` to toggle that setting

It is important to distinguish slash commands from the
[widget system](/subsystems/widgets.md). Slash commands essentially
**do not send** messages (and could have very well had their
own "command prompt" (but don't), since they have nothing to do with
message sending), while widgets are special kinds of messages.

### Data flow

These commands have client-side support in `zcommands.js`.
They send commands to the server using the `/json/command`
endpoint.

In the case of "/ping", the server code in `zcommand.py`
basically just acks the client. The client then computes
the round trip time and shows a little message above
the compose box that the user can see and then dismiss.

For commands like "/light" and "/dark", the server does
a little bit of logic to toggle the user's dark theme
setting, and this is largely done inside `zcommand.py`.
The server sends a very basic response, and then
the client actually changes the display colors. The
client also shows the user a little message above
the compose box instructing them how to reverse the
change.

(It's possible that we don't really need a general
`/json/zcommand` endpoint for these, and we
may decide later to just use custom
API endpoints for each command. There's some logic
in having a central API for these, though, since they
are typically things that only UI-based clients will
invoke, and they may share validation code.)

It is the client's responsibility to correctly detect and
process when a user uses a slash command, and not instead
send a message with the raw content.

## Typeahead

Typeahead for both slash commands (and widgets) is implemented
via the `slash_commands` object in `web/src/composebox_typeahead.js`.
