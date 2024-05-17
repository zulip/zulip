# Sending messages

While sending a message in a chat product might seem simple, there's a
lot of underlying complexity required to make a professional-quality
experience.

This document aims to explain conceptually what happens when a message
is sent in Zulip, and why that is correct behavior. It assumes the
reader is familiar with our
[real-time sync system](events-system.md) for
server-to-client communication and
[new application feature tutorial](../tutorials/new-feature-tutorial.md),
and we generally don't repeat the content discussed there.

## Message lists

This is just a bit of terminology: A "message list" is what Zulip
calls the frontend concept of a (potentially narrowed) message feed.
There are 3 related structures:

- A `message_list_data` just has the sequencing data of which message
  IDs go in what order.
- A `message_list` is built on top of `message_list_data` and
  additionally contains the data for a visible-to-the-user message list
  (E.g. where trailing bookends should appear, a selected message,
  etc.).
- A `message_list_view` is built on top of `message_list` and
  additionally contains rendering details like a window of up to 400
  messages that is present in the DOM at the time, scroll position
  controls, etc.

(This should later be expanded into a full article on message lists
and narrowing).

## Compose area

The compose box does a lot of fancy things that are out of scope for
this article. But it also does a decent amount of client-side
validation before sending a message off to the server, especially
around mentions (E.g. checking the stream name is a valid stream,
displaying a warning about the number of recipients before a user can
use `@**all**` or mention a user who is not subscribed to the current
stream, etc.).

## Backend implementation

The backend flow for sending messages is similar in many ways to the
process described in our
[new application feature tutorial](../tutorials/new-feature-tutorial.md).
This section details the ways in which it is different:

- There is significant custom code inside the `process_message_event`
  function in `zerver/tornado/event_queue.py`. This custom code has a
  number of purposes:
  - Triggering [email and mobile push
    notifications](notifications.md) for any users who
    do not have active clients and have settings of the form "push
    notifications when offline". In order to avoid doing any real
    computational work inside the Tornado codebase, this logic aims
    to just do the check for whether a notification should be
    generated, and then put an event into an appropriate
    [queue](queuing.md) to actually send the message.
    See `maybe_enqueue_notifications` and `zerver/lib/notification_data.py` for
    this part of the logic.
  - Splicing user-dependent data (E.g. `flags` such as when the user
    was `mentioned`) into the events.
  - Handling the [local echo details](#local-echo).
  - Handling certain client configuration options that affect
    messages. E.g. determining whether to send the
    plaintext/Markdown raw content or the rendered HTML (e.g. the
    `apply_markdown` and `client_gravatar` features in our
    [events API docs](https://zulip.com/api/register-queue)).
- Following our standard naming convention, input validation is done
  inside the `check_message` function in `zerver/actions/message_send.py`, which is responsible for
  validating the user can send to the recipient,
  [rendering the Markdown](markdown.md), etc. --
  basically everything that can fail due to bad user input.
- The core `do_send_messages` function (which handles actually sending
  the message) in `zerver/actions/message_send.py` is one of the most optimized and thus complex parts of
  the system. But in short, its job is to atomically do a few key
  things:
  - Store a `Message` row in the database.
  - Store one `UserMessage` row in the database for each user who is
    a recipient of the message (including the sender), with
    appropriate `flags` for whether the user was mentioned, an alert
    word appears, etc. See
    [the section on soft deactivation](#soft-deactivation) for
    a clever optimization we use here that is important for large
    open organizations.
  - Do all the database queries to fetch relevant data for and then
    send a `message` event to the
    [events system](events-system.md) containing the
    data it will need for the calculations described above. This
    step adds a lot of complexity, because the events system cannot
    make queries to the database directly.
  - Trigger any other deferred work caused by the current message,
    e.g. [outgoing webhooks](https://zulip.com/api/outgoing-webhooks)
    or embedded bots.
  - Every query is designed to be a bulk query; we carefully
    unit-test this system for how many database and memcached queries
    it makes when sending messages with large numbers of recipients,
    to ensure its performance.

## Local echo

An essential feature for a good chat is experience is local echo
(i.e. having the message appear in the feed the moment the user hits
send, before the network round trip to the server). This is essential
both for freeing up the compose box (for the user to send more
messages) as well as for the experience to feel snappy.

A sloppy local echo experience (like Google Chat had for over a decade
for emoji) would just render the raw text the user entered in the
browser, and then replace it with data from the server when it
changes.

Zulip aims for a near-perfect local echo experience, which requires is
why our [Markdown system](markdown.md) requires both
an authoritative (backend) Markdown implementation and a secondary
(frontend) Markdown implementation, the latter used only for the local
echo feature. Read our Markdown documentation for all the tricky
details on how that works and is tested.

The rest of this section details how Zulip manages locally echoed
messages.

- The core function in the frontend codebase
  `echo.try_deliver_locally`. This checks whether correct local echo
  is possible (via `markdown.contains_backend_only_syntax`) and useful
  (whether the message would appear in the current view), and if so,
  causes Zulip to insert the message into the relevant feed(s).
- Since the message hasn't been confirmed by the server yet, it
  doesn't have a message ID. The frontend makes one up, via
  `local_message.next_local_id`, by taking the highest message ID it
  has seen and adding the decimal `0.01`. The use of a floating point
  value is critical, because it means the message should sort
  correctly with other messages (at the bottom) and also won't be
  duplicated by a real confirmed-by-the-backend message ID. We choose
  just above the `max_message_id`, because we want any new messages
  that other users send to the current view to be placed after it in
  the feed (this decision is somewhat arbitrary; in any case we'll
  resort it to its proper place once it is confirmed by the server.
  We do it this way to minimize messages jumping around/reordering
  visually).
- The `POST /messages` API request to the server to send the message
  is passed two special parameters that clients not implementing local
  echo don't use: `queue_id` and `local_id`. The `queue_id` is the ID
  of the client's event queue; here, it is used just as a unique
  identifier for the specific client (e.g. a browser tab) that sent
  the message. And the `local_id` is, by the construction above, a
  unique value within that namespace identifying the message.
- The `do_send_messages` backend code path includes the `queue_id` and
  `local_id` in the data it passes to the
  [events system](events-system.md). The events
  system will extend the `message` event dictionary it delivers to
  the client containing the `queue_id` with `local_message_id` field,
  containing the `local_id` that the relevant client used when sending
  the message. This allows the client to know that the `message`
  event it is receiving is the same message it itself had sent.
- Using that information, rather than adding the "new message" to the
  relevant message feed, it updates the (locally echoed) message's
  properties (at the very least, message ID and timestamp) and
  rerenders it in any message lists where it appears. This is
  primarily done in the `process_from_server` function in
  `web/src/echo.js`.

### Local echo in message editing

Zulip also supports local echo in the message editing code path for
edits to just the content of a message. The approach is analogous
(using `markdown.contains_backend_only_syntax`, etc.)), except we
don't need any of the `local_id` tracking logic, because the message
already has a permanent message id; as a result, the whole
implementation was under 150 lines of code.

## Putting it all together

This section just has a brief review of the sequence of steps all in
one place:

- User hits send in the compose box.
- Compose box validation runs; if it passes, the browser locally
  echoes the message and then sends a request to the `POST /messages`
  API endpoint.
- The Django URL routes and middleware run, and eventually call the
  `send_message_backend` view function in `zerver/views/messages.py`.
  (Alternatively, for an API request to send a message via Zulip's
  REST API, things start here).
- `send_message_backend` does some validation before triggering the
  `check_message` + `do_send_messages` backend flow.
- That backend flow saves the data to the database and triggers a
  `message` event in the `notify_tornado` queue (part of the events
  system).
- The events system processes, and dispatches that event to all
  clients subscribed to receive notifications for users who should
  receive the message (including the sender). As a side effect, it
  adds queue items to the email and push notification queues (which,
  in turn, may trigger those notifications).
  - Other clients receive the event and display the new message.
  - For the client that sent the message, it instead replaces its
    locally echoed message with the final message it received back
    from the server (it indicates this to the sender by adding a
    display timestamp to the message).
- The `send_message_backend` view function returns
  a 200 `HTTP` response; the client receives that response and mostly
  does nothing with it other than update some logging details. (This
  may happen before or after the client receives the event notifying
  it about the new message via its event queue.)

## Message editing

Message editing uses a very similar principle to how sending messages
works. A few details are worth mentioning:

- `maybe_enqueue_notifications_for_message_update` is an analogue of
  `maybe_enqueue_notifications`, and exists to handle cases like a
  user was newly mentioned after the message is edited (since that
  should trigger email/push notifications, even if the original
  message didn't have one).
- We use a similar technique to what's described in the local echo
  section for doing client-side rerendering to update the message feed.
- In the default configuration, Zulip stores the message edit history
  (which is useful for forensics but also exposed in the UI), in the
  `message.edit_history` attribute.
- We support topic editing, including bulk-updates moving several
  messages between topics.

### Inline URL previews

Zulip's inline URL previews feature (`zerver/lib/url_preview/`) uses
variant of the message editing/local echo behavior. The reason is
that for inline URL previews, the backend needs to fetch the content
from the target URL, and for slow websites, this could result in a
significant delay in rendering the message and delivering it to other
users.

- For this case, Zulip's backend Markdown processor will render the
  message without including the URL embeds/previews, but it will add a
  deferred work item into the `embed_links` queue.

- The [queue processor](queuing.md) for the
  `embed_links` queue will fetch the URLs, and then if they return
  results, rerun the Markdown processor and notify clients of the
  updated message `rendered_content`.

- We reuse the `update_message` framework (used for
  Zulip's message editing feature) in order to avoid needing custom code
  to implement the notification-and-rerender part of this implementation.

## Soft deactivation

This section details a somewhat subtle issue: How Zulip uses a
user-invisible technique called "soft deactivation" to handle
scalability to communities with many thousands of inactive users.

For background, Zulip’s threading model requires tracking which
individual messages each user has received and read (in other chat
products, the system either doesn’t track what the user has read at
all, or just needs to store a pointer for “how far the user has read”
in each room, channel, or stream).

We track these data in the backend in the `UserMessage` table, storing
rows `(message_id, user_id, flags)`, where `flags` is 32 bits of space
for boolean data like whether the user has read or starred the
message. All the key queries needed for accessing message history,
full-text search, and other key features can be done efficiently with
the database indexes on this table (with joins to the `Message` table
containing the actual message content where required).

The downside of this design is that when a new message is sent to a
stream with `N` recipients, we need to write `N` rows to the
`UserMessage` table to record those users receiving those messages.
Each row is just 3 integers in size, but even with modern databases
and SSDs, writing thousands of rows to a database starts to take a few
seconds.

This isn’t a problem for most Zulip servers, but is a major problem
for communities like chat.zulip.org, where there might be 10,000s of
inactive users who only stopped by briefly to check out the product or
ask a single question, but are subscribed to whatever the default
streams in the organization are.

The total amount of work being done here was acceptable (a few seconds
of total CPU work per message to large public streams), but the
latency was unacceptable: The server backend was introducing a latency
of about 1 second per 2000 users subscribed to receive the message.
While these delays may not be immediately obvious to users (Zulip,
like many other chat applications,
[local echoes](markdown.md) messages that a user sends
as soon as the user hits “Send”), latency beyond a second or two
significantly impacts the feeling of interactivity in a chat
experience (i.e. it feels like everyone takes a long time to reply to
even simple questions).

A key insight for addressing this problem is that there isn’t much of
a use case for long chat discussions among 1000s of users who are all
continuously online and actively participating. Streams with a very
large number of active users are likely to only be used for occasional
announcements, where some latency before everyone sees the message is
fine. Even in giant organizations, almost all messages are sent to
smaller streams with dozens or hundreds of active users, representing
some organizational unit within the community or company.

However, large, active streams are common in open source projects,
standards bodies, professional development groups, and other large
communities with the rough structure of the Zulip development
community. These communities usually have thousands of user accounts
subscribed to all the default streams, even if they only have dozens
or hundreds of those users active in any given month. Many of the
other accounts may be from people who signed up just to check the
community out, or who signed up to ask a few questions and may never
be seen again.

The key technical insight is that if we can make the latency scale
with the number of users who actually participate in the community,
not the total size of the community, then our database write limited
send latency of 1 second per 2000 users is totally fine. But we need
to do this in a way that doesn’t create problems if any of the
thousands of “inactive” users come back (or one of the active users
sends a direct message to one of the inactive users), since it’s
impossible for the software to know which users are eventually coming
back or will eventually be interacted with by an existing user.

We solved this problem with a solution we call “soft deactivation”;
users that are soft-deactivated consume less resources from Zulip in a
way that is designed to be invisible both to other users and to the
user themself. If a user hasn’t logged into a given Zulip
organization for a few weeks, they are tagged as soft-deactivated.

The way this works internally is:

- We (usually) skip creating UserMessage rows for soft-deactivated
  users when a message is sent to a stream where they are subscribed.

- If/when the user ever returns to Zulip, we can at that time
  reconstruct the UserMessage rows that they missed, and create the rows
  at that time (or, to avoid a latency spike if/when the user returns to
  Zulip, this work can be done in a nightly cron job). We can construct
  those rows later because we already have the data for when the user
  might have been subscribed or unsubscribed from streams by other
  users, and, importantly, we also know that the user didn’t interact
  with the UI since the message was sent (and thus we can safely assume
  that the messages have not been marked as read by the user). This is
  done in the `add_missing_messages` function, which is the core of the
  soft-deactivation implementation.

- The “usually” above is because there are a few flags that result
  from content in the message (e.g., a message that mentions a user
  results in a “mentioned” flag in the UserMessage row), that we need to
  keep track of. Since parsing a message can be expensive (>10ms of
  work, depending on message content), it would be too inefficient to
  need to re-parse every message when a soft-deactivated user comes back
  to Zulip. Conveniently, those messages are rare, and so we can just
  create UserMessage rows which would have “interesting” flags at the
  time they were sent without any material performance impact. And then
  `add_missing_messages` skips any messages that already have a
  `UserMessage` row for that user when doing its backfill.

The end result is the best of both worlds:

- Nobody's view of the world is different because the user was
  soft-deactivated (resulting in no visible user-experience impact), at
  least if one is running the cron job. If one does not run the cron
  job, then users returning after being away for a very long time will
  potentially have a (very) slow loading experience as potentially
  100,000s of UserMessage rows might need to be reconstructed at once.
- On the latency-sensitive message sending and fanout code path, the
  server only needs to do work for users who are currently interacting
  with Zulip.

Empirically, we've found this technique completely resolved the "send
latency" scaling problem. The latency of sending a message to a stream
now scales only with the number of active subscribers, so one can send
a message to a stream with 5K subscribers of which 500 are active, and
it’ll arrive in the couple hundred milliseconds one would expect if
the extra 4500 inactive subscribers didn’t exist.

There are a few details that require special care with this system:

- [Email and mobile push
  notifications](notifications.md). We need to make
  sure these are still correctly delivered to soft-deactivated users;
  making this work required careful work for those code paths that
  assumed a `UserMessage` row would always exist for a message that
  triggers a notification to a given user.
- Digest emails, which use the `UserMessage` table extensively to
  determine what has happened in streams the user can see. We can use
  the user's subscriptions to construct what messages they should have
  access to for this feature.
- Soft-deactivated users experience high loading latency when
  returning after being idle for months. We optimize this by
  triggering a soft reactivation for users who receive email or push
  notification for direct messages or personal mentions, or who
  request a password reset, since these are good leading indicators
  that a user is likely to return to Zulip.
