# Sending messages

While sending a message in a chat product might seem simple, there's a
lot of underlying complexity required to make a professional-quality
experience.

This document aims to explain conceptually what happens when a message
is sent in Zulip, and why that is correct behavior.  It assumes the
reader is familiar with our
[real-time sync system](../subsystems/events-system.html) for
server-to-client communication and
[new application feature tutorial](../tutorials/new-feature-tutorial.html),
and we generally don't repeat the content discussed there.

## Message lists

This is just a bit of terminology: A "message list" is what Zulip
calls the frontend concept of a (potentially narrowed) message feed.
There are 3 related structures:
* A `message_list_data` just has the sequencing data of which message
IDs go in what order.
* A `message_list` is built on top of `message_list_data` and
additionally contains the data for a visible-to-the-user message list
(E.g. where trailing bookends should appear, a selected message,
etc.).
* A `message_list_view` is built on top of `message_list` and
additionally contains rendering details like a window of up to 400
messages that is present in the DOM at the time, scroll position
controls, etc.

(This should later be expanded into a full article on message lists
and narrowing).

## Compose area

The compose box does a lot of fancy things that are out of scope for
this article.  But it also does a decent amount of client-side
validation before sending a message off to the server, especially
around mentions (E.g. checking the stream name is a valid stream,
displaying a warning about the number of recipients before a user can
use `@**all**` or mention a user who is not subscribed to the current
stream, etc.).

## Backend implementation

The backend flow for sending messages is similar in many ways to the
process described in our
[new application feature tutorial](../tutorials/new-feature-tutorial.html).
This section details the ways in which it is different:

* There is significant custom code inside the `process_message_event`
function in `zerver/tornado/event_queue.py`.  This custom code has a
number of purposes:
   * Triggering email and mobile push notifications for any users who
     do not have active clients and have settings of the form "push
     notifications when offline".  In order to avoid doing any real
     computational work inside the Tornado codebase, this logic aims
     to just do the check for whether a notification should be
     generated, and then put an event into an appropriate
     [queue](../subsystems/queuing.html) to actually send the
     message.  See `maybe_enqueue_notifications` and related code for
     this part of the logic.
   * Splicing user-dependent data (E.g. `flags` such as when the user
   was `mentioned`) into the events.
   * Handling the [local echo details](#local-echo).
   * Handling certain client configuration options that affect
     messages.  E.g. determining whether to send the
     plaintext/markdown raw content or the rendered HTML (e.g. the
     `apply_markdown` and `client_gravatar` features in our
     [events API docs](https://zulipchat.com/api/register-queue)).
* The webapp [uses websockets](#websockets) for client/server
  interaction for sending messages.
* Following our standard naming convention, input validation is done
  inside the `check_message` function, which is responsible for
  validating the user can send to the recipient (etc.),
  [rendering the markdown](../subsystems/markdown.html), etc. --
  basically everything that can fail due to bad user input.
* The core `do_send_messages` function (which handles actually sending
  the message) is one of the most optimized and thus complex parts of
  the system.  But in short, its job is to atomically do a few key
  things:
   * Store a `Message` row in the database.
   * Store one `UserMessage` row in the database for each user who is
     a recipient of the message (including the sender), with
     appropriate `flags` for whether the user was mentioned, an alert
     word appears, etc.
   * Do all the database queries to fetch relevant data for and then
     send a `message` event to the
     [events system](../subsystems/events-system.html) containing the
     data it will need for the calculations described above.  This
     step adds a lot of complexity, because the events system cannot
     make queries to the database directly.
   * Trigger any other deferred work caused by the current message,
     e.g. [outgoing webhooks](https://zulipchat.com/api/outgoing-webhooks)
     or embedded bots.
   * Every query is designed to be a bulk query; we carefully
     unit-test this system for how many database and memcached queries
     it makes when sending messages with large numbers of recipients,
     to ensure its performance.

### Websockets

For the webapp only, we use WebSockets rather than standard HTTPS API
requests for triggering message sending.  This is a design feature we
are very ambivalent about; it has some slight latency benefits, but is
also features extra complexity and some mostly-unmaintained
dependencies (e.g. `sockjs-tornado`).  But in short, this system works
as follows:
* Requests are sent from the webapp to the backend via the `sockjs`
library (on the frontend) and `sockjs-tornado` (on the backend).  This
ends up calling a handler in our Tornado codebase
(`zerver/tornado/socket.py`), which immediately puts the request into
the `message_sender` queue.
* The `message_sender` [queue processor](../subsystems/queuing.html)
reformats the request into a Django `HttpRequest` object with a fake
`SOCKET` HTTP method (which is why these requests appear as `SOCKET`
in our server logs), calls the Django `get_response` method on that
request, and returns the response to Tornado via the `tornado_return`
queue.
* Tornado then sends the result (success or error) back to the client
via the relevant WebSocket connection.
* `sockjs` automatically handles for us a fallback to longpolling in
the event that a WebSockets connection cannot be opened successfully
(which despite WebSockets being many years old is still a problem on
some networks today!).

## Local echo

An essential feature for a good chat is experience is local echo
(i.e. having the message appear in the feed the moment the user hits
send, before the network round trip to the server).  This is essential
both for freeing up the compose box (for the user to send more
messages) as well as for the experience to feel snappy.

A sloppy local echo experience (like Google Chat had for over a decade
for emoji) would just render the raw text the user entered in the
browser, and then replace it with data from the server when it
changes.

Zulip aims for a near-perfect local echo experience, which requires is
why our [markdown system](../subsystems/markdown.html) requires both
an authoritative (backend) markdown implementation and a secondary
(frontend) markdown implementation, the latter used only for the local
echo feature.  Read our markdown documentation for all the tricky
details on how that works and is tested.

The rest of this section details how Zulip manages locally echoed
messages.

* The core function in the frontend codebase
  `echo.try_deliver_locally`.  This checks whether correct local echo
  is possible (via `markdown.contains_backend_only_syntax`) and useful
  (whether the message would appear in the current view), and if so,
  causes Zulip to insert the message into the relevant feed(s).
* Since the message hasn't been confirmed by the server yet, it
  doesn't have a message ID.  The frontend makes one up, via
  `local_message.next_local_id`, by taking the highest message ID it
  has seen and adding the decimal `0.01`.  The use of a floating point
  value is critical, because it means the message should sort
  correctly with other messages (at the bottom) and also won't be
  duplicated by a real confirmed-by-the-backend message ID.  We choose
  just above the `max_message_id`, because we want any new messages
  that other users send to the current view to be placed after it in
  the feed (this decision is someone arbitrary; in any case we'll
  resort it to its proper place once it is confirmed by the server.
  We do it this way to minimize messages jumping around/reordering
  visually).
* The `POST /messages` API request to the server to send the message
  is passed two special parameters that clients not implementing local
  echo don't use: `queue_id` and `local_id`.  The `queue_id` is the ID
  of the client's event queue; here, it is used just as a unique
  identifier for the specific client (e.g. a browser tab) that sent
  the message.  And the `local_id` is, by the construction above, a
  unique value within that namespace identifying the message.
* The `do_send_messages` backend code path includes the `queue_id` and
  `local_id` in the data it passes to the
  [events system](../subsystems/events-system.html).  The events
  system will extend the `message` event dictionary it delivers to
  the client containing the `queue_id` with `local_message_id` field,
  containing the `local_id` that the relevant client used when sending
  the message.  This allows the client to know that the `message`
  event it is receiving is the same message it itself had sent.
* Using that information, rather than adding the "new message" to the
  relevant message feed, it updates the (locally echoed) message's
  properties (at the very least, message ID and timestamp) and
  rerenders it in any message lists where it appears.  This is
  primarily done in `exports.process_from_server` in
  `static/js/echo.js`.

## Putting it all together

This section just has a brief review of the sequence of steps all in
one place:
* User hits send in the compose box.
* Compose box validation runs; if passes, it locally echoes the
  message and sends websocket message to Tornado
* Tornado converts websocket message to a `message_sender` queue item
* `message_sender` queue processor turns the queue item into a Django
`HttpRequest` and calls Django's main response handler
* The Django URL routes and middleware run, and eventually calls the
  `send_message_backend` view function in `zerver/views/messages.py`.
  (Alternatively, for an API request to send a message via the HTTP
  API, things start here).
* `send_message_backend` does some validation before triggering the
`check_message` + `do_send_messages` backend flow.
* That backend flow saves the data to the database and triggers a
  `message` event in the `notify_tornado` queue (part of the events
  system).
* The events system processes, and dispatches that event to all
  clients subscribed to receive notifications for users who should
  receive the message (including the sender).  As a side effect, it
  adds queue items to the email and push notification queues (which,
  in turn, may trigger those notifications).
  * Other receive the event and display the new message.
  * For the client that sent the message, it instead replaces its
    locally echoed message with the final message it received back
    from the server (it indicates this to the sender by adding a
    display timestamp to the message).
* For an API client, the `send_message_backend` view function returns
  a 200 `HTTP` response; the client receives that response and mostly
  does nothing with it other than update some logging details.  (This
  may happen before or after the client receives the event notifying
  it about the new message via its event queue.)
* For a browser (websockets sender), the client receives the
  equivalent of the HTTP response via a websockets message from
  Tornado (which, in turn, got that via the `tornado_return` queue).

## Error handling

When there's an error trying to send a message, it's important to not
lose the text the user had composed.  Zulip handles this with a few
approaches:

* The data for a message in the process of being sent are stored in
  browser local storage (see .e.g. `_save_localstorage_requests` in
  `static/js/socket.js`), so that the client can retransmit as
  appropriate, even if the browser reloads in the meantime.
* Additionally, Zulip renders UI for editing/retransmitting/resending
  messages that had been locally echoed on top of those messages, in
  red.

## Message editing

Message editing uses a very similar principle to how sending messages
works.  A few details are worth mentioning:

* `maybe_enqueue_notifications_for_message_update` is an analogue of
  `maybe_enqueue_notifications`, and exists to handle cases like a
  user was newly mentioned after the message is edited (since that
  should trigger email/push notifications, even if the original
  message didn't have one).
* We use a similar technique to what's described in the local echo
  section for doing client-side rerendering to update the message feed.
* In the default configuration, Zulip stores the message edit history
  (which is useful for forensics but also exposed in the UI), in the
  `message.edit_history` attribute.
* We support topic editing, including bulk-updates moving several
  messages between topics.

### Inline URL previews

Zulip's inline URL previews feature (`zerver/lib/url_preview/`) uses
variant of the message editing/local echo behavior.  The reason is
that for inline URL previews, the backend needs to fetch the content
from the target URL, and for slow websites, this could result in a
significant delay in rendering the message and delivering it to other
users.

* For this case, Zulip's backend markdown processor will render the
message without including the URL embeds/previews, but it will add a
deferred work item into the `embed_links` queue.

* The [queue processor](../subsystems/queuing.html) for the
`embed_links` queue will fetch the URLs, and then if they return
results, rerun the markdown processor and notify clients of the
updated message `rendered_content`.

* We reuse the `update_message` framework (used for
Zulip's message editing feature) in order to avoid needing custom code
to implement the notification-and-rerender part of this implementation.
