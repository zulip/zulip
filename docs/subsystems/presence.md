# Presence

This document explains the model for Zulip's presence.

In a chat tool like Zulip, users expect to see the “presence” status
of other users: is the person I want to talk to currently online? If
not, were they last online 5 minutes ago, or more like an hour ago, or
a week?  Presence helps set expectations for whether someone is likely
to respond soon.  To a user, this feature can seem like a simple thing
that should be easy.  But presence is actually one of the hardest
scalability problems for a team chat tool like Zulip.

There's a lot of performance-related details in the backend and
network protocol design that we won't get into here.  The focus of
this is what one needs to know to correctly implement a Zulip client's
presence implementation (e.g. webapp, mobile app, terminal client, or
other tool that's intended to represent whether a user is online and
using Zulip).

A client should report to the server every minute a `POST` request to
`/users/me/presence`, containing the current user's status.  The
requests contains a few parameters.  The most important is "status",
which had 2 valid values:

* "active" -- this means the user has interacted with the client
  recently.  We use this for the "green" state in the webapp.
* "idle" -- the user has not interacted with the client recently.
  This is important for the case where a user left a Zulip tab open on
  their desktop at work and went home for the weekend.  We use this
  for the "orange" state in the webapp.

The client receives in the response to that request a data set that,
for each user, contains their status and timestamp that we last heard
from that client.  There are a few important details to understand
about that data structure:

* It's really important that the timestamp is the last time we heard
  from the client.  A client can only interpret the status to display
  about another user by doing a simple computation using the (status,
  timestamp) pair.  E.g. a user who last used Zulip 1 week ago will
  have a timestamp of 1 week ago and a status of "active".  Why?
  Because this correctly handles the race conditions.  For example, if
  the threshhold for displaying a user as "offline" was 5 minutes
  since the user was last online, the client can at any time
  accurately compute whether that user is offline (even if the last
  data from the server was 45 seconds ago, and the user was last
  online 4:30 before the client received that server data).
* The `status_from_timestamp` function in `static/js/presence.js` is
  useful sample code; the `OFFLINE_THRESHOLD_SECS` check is critical
  to correct output.
* We provide the data for e.g. whether the user was online on their
  desktop or the mobile app, but for a basic client, you will likely
  only want to parse the "aggregated" key, which shows the summary
  answer for "is this user online".

