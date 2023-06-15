# Real-time push and events

Zulip's "events system" is the server-to-client push system that
powers our real-time sync. This document explains how it works; to
read an example of how a complete feature using this system works,
check out the
[new application feature tutorial](../tutorials/new-feature-tutorial.md).

Any single-page web application like Zulip needs a story for how
changes made by one client are synced to other clients, though having
a good architecture for this is particularly important for a chat tool
like Zulip, since the state is constantly changing. When we talk
about clients, think a browser tab, mobile app, or API bot that needs
to receive updates to the Zulip data. The simplest example is a new
message being sent by one client; other clients must be notified in
order to display the message. But a complete application like Zulip
has dozens of different types of data that need to be synced to other
clients, whether it be new streams, changes in a user's name or
avatar, settings changes, etc. In Zulip, we call these updates that
need to be sent to other clients **events**.

An important thing to understand when designing such a system is that
events need to be synced to every client that has a copy of the old
data if one wants to avoid clients displaying inaccurate data to
users. So if a user has two browser windows open and sends a message,
every client controlled by that user as well as any recipients of the
message, including both of those two browser windows, will receive
that event. (Technically, we don't need to send events to the client
that triggered the change, but this approach saves a bunch of
unnecessary duplicate UI update code, since the client making the
change can just use the same code as every other client, maybe plus a
little notification that the operation succeeded).

Architecturally, there are a few things needed to make a successful
real-time sync system work:

- **Generation**. Generating events when changes happen to data, and
  determining which users should receive each event.
- **Delivery**. Efficiently delivering those events to interested
  clients, ideally in an exactly-once fashion.
- **UI updates**. Updating the UI in the client once it has received
  events from the server.

Reactive JavaScript libraries like React and Vue can help simplify the
last piece, but there aren't good standard systems for doing
generation and delivery, so we have to build them ourselves.

This document discusses how Zulip solves the generation and delivery
problems in a scalable, correct, and predictable way.

## Generation system

Zulip's generation system is built around a Python function,
`send_event(realm, event, users)`. It accepts the realm (used for
sharding), the event data structure (just a Python dictionary with
some keys and value; `type` is always one of the keys but the rest
depends on the specific event) and a list of user IDs for the users
whose clients should receive the event. In special cases such as
message delivery, the list of users will instead be a list of dicts
mapping user IDs to user-specific data like whether that user was
mentioned in that message. The data passed to `send_event` are simply
marshalled as JSON and placed in the `notify_tornado` RabbitMQ queue
to be consumed by the delivery system.

Usually, this list of users is one of 3 things:

- A single user (e.g. for user-level settings changes).
- Everyone in the realm (e.g. for organization-level settings changes,
  like new realm emoji).
- Everyone who would receive a given message (for messages, emoji
  reactions, message editing, etc.); i.e. the subscribers to a stream
  or the people on a direct message thread.

It is the responsibility of the caller of `send_event` to choose the
list of user IDs correctly. There can be security problems if e.g. an
event containing direct message content is sent to the entire
organization. However, if an event isn't sent to enough clients,
there will likely be user-visible real-time sync bugs.

Most of the hard work in event generation is about defining consistent
event dictionaries that are clear, readable, will be useful to the
wide range of possible clients, and make it easy for developers.

## Delivery system

Zulip's event delivery (real-time push) system is based on Tornado,
which is ideal for handling a large number of open requests. Details
on Tornado are available in the
[architecture overview](../overview/architecture-overview.md), but in short it
is good at holding open a large number of connections for a long time.
The complete system is about 2000 lines of code in `zerver/tornado/`,
primarily `zerver/tornado/event_queue.py`.

Zulip's event delivery system is based on "long-polling"; basically
clients make `GET /json/events` calls to the server, and the server
doesn't respond to the request until it has an event to deliver to the
client. This approach is reasonably efficient and works everywhere
(unlike websockets, which have a decreasing but nonzero level of
client compatibility problems).

For each connected client, the **event queue server** maintains an
**event queue**, which contains any events that are to be delivered to
that client which have not yet been acknowledged by that client.
Ignoring the subtle details around error handling, the protocol is
pretty simple; when a client does a `GET /json/events` call, the
server checks if there are any events in the queue. If there are, it
returns the events immediately. If there aren't, it records that
queue as having a waiting client (often called a `handler` in the
code).

When it pulls an event off the `notify_tornado` RabbitMQ queue, it
simply delivers the event to each queue associated with one of the
target users. If the queue has a waiting client, it breaks the
long-poll connection by returning an HTTP response to the waiting
client request. If there is no waiting client, it simply pushes the
event onto the queue.

When starting up, each client makes a `POST /json/register` to the
server, which creates a new event queue for that client and returns the
`queue_id` as well as an initial `last_event_id` to the client (it can
also, optionally, fetch the initial data to save an RTT and avoid
races; see the below section on initial data fetches for details on
why this is useful). Once the event queue is registered, the client
can just do an infinite loop calling `GET /json/events` with those
parameters, updating `last_event_id` each time to acknowledge any
events it has received (see `call_on_each_event` in the
[Zulip Python API bindings][api-bindings-code] for a complete example
implementation). When handling each `GET /json/events` request, the
queue server can safely delete any events that have an event ID less
than or equal to the client's `last_event_id` (event IDs are just a
counter for the events a given queue has received.)

If network failures were impossible, the `last_event_id` parameter in
the protocol would not be required, but it is important for enabling
exactly-once delivery in the presence of potential failures. (Without
it, the queue server would have to delete events from the queue as
soon as it attempted to send them to the client; if that specific HTTP
response didn't reach the client due to a network TCP failure, then
those events could be lost).

[api-bindings-code]: https://github.com/zulip/python-zulip-api/blob/main/zulip/zulip/__init__.py

The queue servers are a very high-traffic system, processing at a
minimum one request for every message delivered to every Zulip client.
Additionally, as a workaround for low-quality NAT servers that kill
HTTP connections that are open without activity for more than 60s, the
queue servers also send a heartbeat event to each queue at least once
every 45s or so (if no other events have arrived in the meantime).

To avoid a large memory and other resource leak, the queues are
garbage collected after (by default) 10 minutes of inactivity from a
client, under the theory that the client has likely gone off the
Internet (or no longer exists) access; this happens constantly. If
the client returns, it will receive a "queue not found" error when
requesting events; its handler for this case should just restart the
client / reload the browser so that it refetches initial data the same
way it would on startup. Since clients have to implement their
startup process anyway, this approach adds minimal technical
complexity to clients. A nice side effect is that if the event queue
server (which stores queues in memory) were to crash and lose
its data, clients would recover, just as if they had lost Internet
access briefly (there is some DoS risk to manage, though).

Note that the garbage-collection system has hooks that are important
for the implementation of [notifications](notifications.md).

(The event queue server is designed to save any event queues to disk
and reload them when the server is restarted, and catches exceptions
carefully, so such incidents are very rare, but it's nice to have a
design that handles them without leaving broken out-of-date clients
anyway).

## The initial data fetch

When a client starts up, it usually wants to get 2 things from the
server:

- The "current state" of various pieces of data, e.g. the current
  settings, set of users in the organization (for typeahead), stream,
  messages, etc. (aka the "initial state").
- A subscription to receive updates to those data when they are
  changed by a client (aka an event queue).

Ideally, one would get those two things atomically, i.e. if some other
user changes their name, either the name change happens after the
fetch (and thus the old name is in the initial state and there will be
an event in the queue for the name change) or before (the new name is
in the initial state, and there is no event for that name change in
the queue).

Achieving this atomicity goals means we save a huge amount of work
that the N clients for Zulip don't need to worry about a wide range of
potential rare and hard to reproduce race conditions; we just have to
implement things correctly once in the Zulip server.

This is quite challenging to do technically, because fetching the
initial state for a complex web application like Zulip might involve
dozens of queries to the database, caches, etc. over the course of
100ms or more, and it is thus nearly impossible to do all of those
things together atomically. So instead, we use a more complicated
algorithm that can produce the atomic result from non-atomic
subroutines. Here's how it works when you make a `register` API
request; the logic is in `zerver/views/events_register.py` and
`zerver/lib/events.py`. The request is directly handled by Django:

- Django makes an HTTP request to Tornado, requesting that a new event
  queue be created, and records its queue ID.
- Django does all the various database/cache/etc. queries to fetch the
  data, non-atomically, from the various data sources (see
  the `fetch_initial_state_data` function).
- Django makes a second HTTP request to Tornado, requesting any events
  that had been added to the Tornado event queue since it
  was created.
- Finally, Django "applies" the events (see the `apply_events`
  function) to the initial state that it fetched. E.g. for a name
  change event, it finds the user data in the `realm_user` data
  structure, and updates it to have the new name.

### Testing

The design above achieves everything we desire, at the cost that we need to
write a correct `apply_events` function. This is a difficult function to
implement correctly, because the situations that it handles almost never
happen (being race conditions) during manual testing. Fortunately, we have
a protocol for testing `apply_events` in our automated backend tests.

#### Overview

Once you are completely confident that an "action function" works correctly
in terms of "normal" operation (which typically involves writing a
full-stack test for the corresponding POST/GET operation), then you will be
ready to write a test in `test_events.py`.

The actual code for a `test_events` test can be quite concise:

```python
def test_default_streams_events(self) -> None:
    stream = get_stream("Scotland", self.user_profile.realm)
    events = self.verify_action(lambda: do_add_default_stream(stream))
    check_default_streams("events[0]", events[0])
    # (some details omitted)
```

The real trick is debugging these tests.

The test example above has three things going on:

- Set up some data (`get_stream`)
- Call `verify_action` with an action function (`do_add_default_stream`)
- Use a schema checker to validate data (`check_default_streams`)

#### verify_action

All the heavy lifting that pertains to `apply_events` happens within the
call to `verify_action`, which is a test helper in the `BaseAction` class
within `test_events.py`.

The `verify_action` function simulates the possible race condition in
order to verify that the `apply_events` logic works correctly in the
context of some action function. To use our concrete example above,
we are seeing that applying the events from the
`do_remove_default_stream` action inside of `apply_events` to a stale
copy of your state results in the same state dictionary as doing the
action and then fetching a fresh copy of the state.

In particular, `verify_action` does the following:

- Call `fetch_initial_state_data` to get the current state.
- Call the action function (e.g. `do_add_default_stream`).
- Capture the events generated by the action function.
- Check the events generated are documented in the [OpenAPI
  schema](../documentation/api.md) defined in
  `zerver/openapi/zulip.yaml`.
- Call `apply_events(state, events)`, to get the resulting "hybrid state".
- Call `fetch_initial_state_data` again to get the "normal state".
- Compare the two results.

In the event that you wrote the `apply_events` logic correctly the
first time, then the two states will be identical, and the
`verify_action` call will succeed and return the events that came from
the action.

Often you will get the `apply_events` logic wrong at first, which will
cause `verify_action` to fail. To help you debug, it will print a diff
between the "hybrid state" and the "normal state" obtained from
calling `fetch_initial_state_data` after the changes. If you encounter a
diff like this, you may be in for a challenging debugging exercise. It
will be helpful to re-read this documentation to understand the rationale
behind the `apply_events` function. It may also be helpful to read the code
for `verify_action` itself. Finally, you may want to ask for help on chat.

Before we move on to the next step, it's worth noting that `verify_action`
only has one required parameter, which is the action function. We
typically express the action function as a lambda, so that we
can pass in arguments:

```python
events = self.verify_action(lambda: do_add_default_stream(stream))
```

There are some notable optional parameters for `verify_action`:

- `state_change_expected` must be set to `False` if your action
  doesn't actually require state changes for some reason; otherwise,
  `verify_action` will complain that your test doesn't really
  exercise any `apply_events` logic. Typing notifications (which
  are ephemeral) are a common place where we use this.

- `num_events` will tell `verify_action` how many events the
  `hamlet` user will receive after the action (the default is 1).

- parameters such as `client_gravatar` and `slim_presence` get
  passed along to `fetch_initial_state_data` (and it's important
  to test both boolean values of these parameters for relevant
  actions).

For advanced use cases of `verify_action`, we highly recommend reading
the code itself in `BaseAction` (in `test_events.py`).

#### Schema checking

The `test_events.py` system has two forms of schema checking. The
first is verifying that you've updated the [GET /events API
documentation](https://zulip.com/api/get-events) to document your new
event's format for benefit of the developers of Zulip's mobile app,
terminal app, and other API clients. See the [API documentation
docs](../documentation/api.md) for details on the OpenAPI
documentation.

The second is higher-detail check inside `test_events` that this
specific test generated the expected series of events. Let's look at
the last line of our example test snippet:

```python
# ...
events = self.verify_action(lambda: do_add_default_stream(stream))
check_default_streams("events[0]", events[0])
```

We have discussed `verify_action` in some detail, and you will
note that it returns the actual events generated by the action
function. It is part of our test discipline in `test_events` to
verify that the events are formatted in a predictable way.

Ideally, we would test that events match the exact data that we
expect, but it can be difficult to do this due to unpredictable
things like database ids. So instead, we just verify the "schema"
of the event(s). We use a schema checker like `check_default_streams`
to validate the types of the data.

If you are creating a new event format, then you will have to
write your own schema checker in `event_schema.py`. Here is
the example relevant to our example:

```python
default_streams_event = event_dict_type(
    required_keys=[
        ("type", Equals("default_streams")),
        ("default_streams", ListType(DictType(basic_stream_fields))),
    ]
)
check_default_streams = make_checker(default_streams_event)
```

Note that `basic_stream_fields` is not shown in these docs. The
best way to understand how to write schema checkers is to read
`event_schema.py`. There is a large block comment at the top of
the file, and then you can skim the rest of the file to see the
patterns.

When you create a new schema checker for a new event, you not only
make the `test_events` test more rigorous, you also allow our other
tools to use the same schema checker to validate event formats in our
node test fixtures and our OpenAPI documentation.

#### Node testing

Once you've completed backend testing, be sure to add an example event
in `web/tests/lib/events.js`, a test of the
`server_events_dispatch.js` code for that event in
`web/tests/dispatch.test.js`, and verify your example
against the two versions of the schema that you declared above using
`tools/check-schemas`.

#### Code coverage

The final detail we need to ensure that `apply_events` always works
correctly is to make sure that we have relevant tests for
every event type that can be generated by Zulip. This can be tested
manually using `test-backend --coverage BaseAction` and then
checking that all the calls to `send_event` are covered. Someday
we'll add automation that verifies this directly by inspecting the
coverage data.

#### page_params

In the Zulip web app, the data returned by the `register` API is
available via the `page_params` parameter.

### Messages

One exception to the protocol described in the last section is the
actual messages. Because Zulip clients usually fetch them in a
separate AJAX call after the rest of the site is loaded, we don't need
them to be included in the initial state data. To handle those
correctly, clients are responsible for discarding events related to
messages that the client has not yet fetched.

Additionally, see
[the main documentation on sending messages](sending-messages.md).

## Schema changes

When changing the format of events sent into Tornado, it's important
to make sure we handle backwards-compatibility properly.

- If we're adding a new event type or new fields to an existing event
  type, we just need to carefully document the changes in the [API
  documentation](../documentation/api.md), being careful to bump
  `API_FEATURE_LEVEL` and include a `**Changes**` entry in the updated
  `GET /events` API documentation. It's also a good idea to and open
  issues with the mobile and terminal projects to notify them.
- If we're making changes that could confuse existing client app logic
  that parses events (E.g. changing the type/meaning of an existing
  field, or removing a field), we need to be very careful, since Zulip
  supports old clients connecting to a modern server. See our
  [release lifecycle](../overview/release-lifecycle.md) documentation
  for more details on the policy. Our technical solution is to add a
  `client_capabilities` flag for the new format and have the code
  continue sending data in the old format for clients that don't
  declare support for the new capability. `bulk_message_deletion` is
  a good example to crib from. (A few years later, we'll make the
  client capability required and remove support for not having it).
- For most event types, Tornado just passes the event through
  transparently, and `event_queue.py` requires no changes.
- However, when changing the format of data used by Tornado code, like
  renaming the `presence_idle_user_ids` field in `message` events, we
  need to be careful, because pre-upgrade events may be present in
  Tornado's queue when we upgrade Tornado. So it's essential to write
  logic in `event_queue.py` to translate the old format into the new
  format, or Tornado may crash when upgrading past the relevant
  commit. We attempt to contain that sort of logic in the `from_dict`
  function (which is used for changing event queue formats) and
  `client_capabilities` conditionals (E.g. in
  `process_deletion_event`). Compatibility code not related to a
  `client_capabilities` entry should be marked with a
  `# TODO/compatibility: ...` comment noting when it can be safely deleted;
  we grep for these comments entries during major releases.
- Schema changes are a sensitive operation, and like with database
  schema changes, it's critical to do thoughtful manual testing.
  E.g. run the mobile app against your test server and verify it
  handles the new event properly, or arrange for your new Tornado code
  to actually process a pre-upgrade event and verify via the browser
  console what came out.
