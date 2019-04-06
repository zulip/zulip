# Typing indicators

Zulip supports a feature called "typing indicators."

Typing indicators are status messages that tell you when
another user is composing a message to you.  Zulip's typing UI
is similar to what you see in other chat/text systems.

This document describes how we have implemented the feature in Zulip,
and our main audience is developers who want to understand the
system and possibly improve it.  This document assumes that the
client is our web app, but any client can play along with this
protocol.

Right now typing indicators are only used in "Private Messages"
views.

There are two major roles for users in this system:

* The "writing user" is composing a message.
* The "receiving user" is waiting to receive a message (or possibly
  ready to shift their attention elsewhere).

Any Zulip user can play either one of these roles, and sometimes
they can be playing both roles at once.  Having said that, you
can generally understand the system in terms of a single message
being composed by the "writing user."

On a high level the typing indicators system works like this:

* The client for the "writing user" sends requests to the server.
* The server broadcasts events to other users.
* The clients for "receiving users" receive events and conditionally
  show typing indicators, depending on where the clients are narrowed.

## Writing user

When a "writing user" starts to compose a message, the client app
sends a request to an endpoint called `/json/typing` with an `op`
of `start` and a list of potential message recipients. The JS
function that facilitates this is called `send_typing_notification_ajax`.

If the "writing user" is composing a long message, we want to send
repeated updates to the server, so that downstream clients know that the
user is still typing.  (Zulip messages tend to be longer than
messages in other chat/text clients, so this detail is important.)

We have a small state machine in `static/js/typing_status.js` that
makes sure subsequent "start" requests get sent out every ten
seconds.  (This document is intended to describe the high level
architecture; the actual time values may be tuned in future releases.
See the constant `TYPING_STARTED_WAIT_PERIOD`, for example.)

If the "writing user" goes more than five seconds without any text
input, then we send a request with an `op` of `stop`.  We also send
"stop" messages when the user explicitly aborts composing a message
by closing the compose box (or other actions).

A common scenario is that a user is just pausing to think for a few
seconds, but they still intend to finish the message.  Of course,
that's hard to distinguish from the scenario of the user got pulled
away from their desk.  For the former case, where the "writing user"
completes the message with lots of pauses for thinking, a series of
"start" and "stop" messages may be sent over time.  Timeout values
reflect tradeoffs, where we have to guess how quickly people type,
how long they pause to think, and how frequently they get interrupted.

## Server

The server piece of typing notificiations is currently pretty
straightforward, since we take advantage of Zulip's
[events system](../subsystems/events-system.html).

We deliberately designed the server piece to be stateless,
which minimizes the possibility of backend bugs and gives clients
more control over the user experience.

As such, the server piece here is basically a single Django view
function with a small bit of library support to send out events
to clients.

Requests come into `/json/typing`.  The view mostly calls out
to `check_send_typing_notification` to do the heavy lifting.

One of the main things that the server does is to simply validate
the recipients with a call to `recipient_for_emails`.  (We should
streamline the payload in the request to have user ids instead of
emails, but of course we will still need to validate recipients.)

Once the request has been validated, the server sends events to
potential recipients of the message.  The event type for that
payload is `typing`.  See the function `do_send_typing_notification`
for more details.

## Receiving user

When a user plays the role of a "receiving user," the client handles
incoming "typing" events from the server, and the client will
display typing notification only when both of these conditions are
true:

* The "writing user" is still likely typing.
* The "receiving user" is in a view where they'd see the eventual
  message.

The client code starts by processing events, and it maintains data
structures, and then it eventually shows or hides status messages.

We'll describe the flow of data through the web app
as a concrete example.

The events will come in to `static/js/server_events_dispatch.js`.
The `stop` and `start` operations get further handled by
`static/js/typing_events.js`.

The main goal is then to triage which events should lead to
display changes.

The web app client maintains a list of incoming "typists" using
code in `static/js/typing_data.js`.  The API here has functions
like the following:

* `add_typist`
* `remove_typist`
* `get_group_typists`
* `get_all_typists`

One subtle thing that the client has to do here is to maintain
timers for typing notifications.  The constant
`TYPING_STARTED_EXPIRY_PERIOD` is used to determine that the
"writing user" has abandoned the message.  Of course, the
"writing user" will also explicitly send us `stop` notifications
at certain times.

When it finally comes to displaying the notification, the web
app eventually calls `render_notifications_for_narrow`.

## Ecosystem

Even though the server is stateless, any developer working on
a client needs to be mindful of timing/network considerations
that affect the overall system.

In general, client developers should agree on timeout parameters
for how frequently we "kickstart" typing notifications for users
sending long messages.  This means standardizing the "writing
user" piece of the system.  It's possible that certain clients
will have slightly different mechanisms for detecting that users
have abandoned messages, but the re-transmit frequency should be
similar.

When implementing the "receiving user" piece, it's important to
realize how clients behave on the other end of the protocol. It's
possible, for example, to never receive a "stop" notification
from a client that was shut down abruptly.  You should allow
reasonable amounts of time for the other side to send notifications,
allowing for network delays and server delays, but you should
not let the notifications become too "sticky" either.

## Roadmap

This document is being written just under a year after typing
indicators were first implemented.  The feature has been popular,
and after some initial cleanup, it has not required a lot of
maintenance.

The most likely big change to typing indicators is that we will
add them for stream conversations.  This will require some thought
for large streams, in terms of both usability and performance.

Another area for refinement is to tune the timing values a bit.
Right now we are probably too aggressive about sending `stop`
messages, when users often are just pausing.  It's possible
to better account for typing speed or other heuristic things
like how much of the message has already been typed.

From an infrastructure perspective, we should be mindful of
bandwidth concerns.  A fairly easy change would be to send
user ids instead of emails.

Some folks may want to turn off typing indicators, so we will
eventually want customized settings here.
