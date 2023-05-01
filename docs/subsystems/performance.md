# Performance and scalability

This page aims to give some background to help prioritize work on the
Zulip's server's performance and scalability. By scalability, we mean
the ability of the Zulip server on given hardware to handle a certain
workload of usage without performance materially degrading.

First, a few notes on philosophy.

- We consider it an important technical goal for Zulip to be fast,
  because that's an important part of user experience for a real-time
  collaboration tool like Zulip. Many UI features in the Zulip web app
  are designed to load instantly, because all the data required for
  them is present in the initial HTTP response, and both the Zulip
  API and web app are architected around that strategy.
- The Zulip database model and server implementation are carefully
  designed to ensure that every common operation is efficient, with
  automated tests designed to prevent the accidental introductions of
  inefficient or excessive database queries. We much prefer doing
  design/implementation work to make requests fast over the operational
  work of running 2-5x as much hardware to handle the same load.

See also [scalability for production users](../production/requirements.md#scalability).

## Load profiles

When thinking about scalability and performance, it's
important to understand the load profiles for production uses.

Zulip servers typically involve a mixture of two very different types
of load profiles:

- Open communities like open source projects, online classes,
  etc. have large numbers of users, many of whom are idle. (Many of
  the others likely stopped by to ask a question, got it answered, and
  then didn't need the community again for the next year). Our own
  [Zulip development community](https://zulip.com/development-community/) is a good
  example for this, with more than 15K total user accounts, of which
  only several hundred have logged in during the last few weeks.
  Zulip has many important optimizations, including [soft
  deactivation](sending-messages.md#soft-deactivation)
  to ensure idle users have minimal impact on both server-side
  scalability and request latency.
- Fulltime teams, like your typical corporate Zulip installation,
  have users who are mostly active for multiple hours a day and sending a
  high volume of messages each. This load profile is most important
  for self-hosted servers, since many of those are used exclusively by
  the employees of the organization running the server.

The zulip.com load profile is effectively the sum of thousands of
organizations from each of those two load profiles.

## Major Zulip endpoints

It's important to understand that Zulip has a handful of endpoints
that result in the vast majority of all server load, and essentially
every other endpoint is not important for scalability. We still put
effort into making sure those other endpoints are fast for latency
reasons, but were they to be 10x faster (a huge optimization!), it
wouldn't materially improve Zulip's scalability.

For that reason, we organize this discussion of Zulip's scalability
around the several specific endpoints that have a combination of
request volume and cost that makes them important.

That said, it is important to distinguish the load associated with an
API endpoint from the load associated with a feature. Almost any
significant new feature is likely to result in its data being sent to
the client in `page_params` or `GET /messages`, i.e. one of the
endpoints important to scalability here. As a result, it is important
to thoughtfully implement the data fetch code path for every feature.

Furthermore, a snappy user interface is one of Zulip's design goals, and
so we care about the performance of any user-facing code path, even
though many of them are not material to scalability of the server.
But only with regard to the requests detailed below, is it worth considering
optimizations which save a few milliseconds that would be invisible to the end user,
if they carry any cost in code readability.

In Zulip's documentation, our general rule is to primarily write facts
that are likely to remain true for a long time. While the numbers
presented here vary with hardware, usage patterns, and time (there's
substantial oscillation within a 24 hour period), we expect the rough
sense of them (as well as the list of important endpoints) is not
likely to vary dramatically over time.

| Endpoint                | Average time | Request volume | Average impact |
| ----------------------- | ------------ | -------------- | -------------- |
| POST /users/me/presence | 25ms         | 36%            | 9000           |
| GET /messages           | 70ms         | 3%             | 2100           |
| GET /                   | 300ms        | 0.3%           | 900            |
| GET /events             | 2ms          | 44%            | 880            |
| GET /user_uploads/\*    | 12ms         | 5%             | 600            |
| POST /messages/flags    | 25ms         | 1.5%           | 375            |
| POST /messages          | 40ms         | 0.5%           | 200            |
| POST /users/me/\*       | 50ms         | 0.04%          | 20             |

The "Average impact" above is computed by multiplying request volume
by average time; this tells you roughly that endpoint's **relative**
contribution to the steady-state total CPU load of the system. It's
not precise -- waiting for a network request is counted the same as
active CPU time, but it's extremely useful for providing intuition for
what code paths are most important to optimize, especially since
network wait is in practice largely waiting for PostgreSQL or
memcached to do work.

As one can see, there are two categories of endpoints that are
important for scalability: those with extremely high request volumes,
and those with moderately high request volumes that are also
expensive. It doesn't matter how expensive, for example,
`POST /users/me/subscriptions` is for scalability, because the volume
is negligible.

### Tornado

Zulip's Tornado-based [real-time push
system](events-system.md), and in particular
`GET /events`, accounts for something like 50% of all HTTP requests to
a production Zulip server. Despite `GET /events` being extremely
high-volume, the typical request takes 1-3ms to process, and doesn't
use the database at all (though it will access `memcached` and
`redis`), so they aren't a huge contributor to the overall CPU usage
of the server.

Because these requests are so efficient from a total CPU usage
perspective, Tornado is significantly less important than other
services like Presence and fetching message history for overall CPU
usage of a Zulip installation.

It's worth noting that most (~80%) Tornado requests end the
longpolling via a `heartbeat` event, which are issued to idle
connections after about a minute. These `heartbeat` events are
useless aside from avoiding problems with networks/proxies/NATs that
are configured poorly and might kill HTTP connections that have been
idle for a minute. It's likely that with some strategy for detecting
such situations, we could reduce their volume (and thus overall
Tornado load) dramatically.

Currently, Tornado is sharded by realm, which is sufficient for
arbitrary scaling of the number of organizations on a multi-tenant
system like zulip.com. With a somewhat straightforward set of work,
one could change this to sharding by `user_id` instead, which will
eventually be important for individual large organizations with many
thousands of concurrent users.

### Presence

`POST /users/me/presence` requests, which submit the current user's
presence information and return the information for all other active
users in the organization, account for about 36% of all HTTP requests
on production Zulip servers. See
[presence](presence.md) for details on this system and
how it's optimized. For this article, it's important to know that
presence is one of the most important scalability concerns for any
chat system, because it cannot be cached long, and is structurally a
quadratic problem.

Because typical presence requests consume 10-50ms of server-side
processing time (to fetch and send back live data on all other active
users in the organization), and are such a high volume, presence is
the single most important source of steady-state load for a Zulip
server. This is true for most other chat server implementations as
well.

There is an ongoing [effort to rewrite the data model for
presence](https://github.com/zulip/zulip/pull/16381) that we expect to
result in a substantial improvement in the per-request and thus total
load resulting from presence requests.

### Fetching page_params

The request to generate the `page_params` portion of `GET /`
(equivalent to the response from [GET
/api/v1/register](https://zulip.com/api/register-queue) used by
mobile/terminal apps) is one of Zulip's most complex and expensive.

Zulip is somewhat unusual among web apps in sending essentially all of the
data required for the entire Zulip web app in this single request,
which is part of why the Zulip web app loads very quickly -- one only
needs a single round trip aside from cacheable assets (avatars, images, JS,
CSS). Data on other users in the organization, streams, supported
emoji, custom profile fields, etc., is all included. The nice thing
about this model is that essentially every UI element in the Zulip
client can be rendered immediately without paying latency to the
server; this is critical to Zulip feeling performant even for users
who have a lot of latency to the server.

There are only a few exceptions where we fetch data in a separate AJAX
request after page load:

- Message history is managed separately; this is why the Zulip web app will
  first render the entire site except for the middle panel, and then a
  moment later render the middle panel (showing the message history).
- A few very rarely accessed data sets like [message edit
  history](https://zulip.com/help/view-a-messages-edit-history) are
  only fetched on demand.
- A few data sets that are only required for administrative settings
  pages are fetched only when loading those parts of the UI.

Requests to `GET /` and `/api/v1/register` that fetch `page_params`
are pretty rare -- something like 0.3% of total requests, but are
important for scalability because (1) they are the most expensive read
requests the Zulip API supports and (2) they can come in a thundering
herd around server restarts (as discussed in [fetching message
history](#fetching-message-history).

The cost for fetching `page_params` varies dramatically based
primarily on the organization's size, varying from 90ms-300ms for a
typical organization but potentially multiple seconds for large open
organizations with 10,000s of users. There is also smaller
variability based on a individual user's personal data state,
primarily in that having 10,000s of unread messages results in a
somewhat expensive query to find which streams/topics those are in.

We consider any organization having normal `page_params` fetch times
greater than a second to be a bug, and there is ongoing work to fix that.

It can help when thinking about this to imagine `page_params` as what
in another web app would have been 25 or so HTTP GET requests, each
fetching data of a given type (users, streams, custom emoji, etc.); in
Zulip, we just do all of those in a single API request. In the
future, we will likely move to a design that does much of the database
fetching work for different features in parallel to improve latency.

For organizations with 10K+ users and many default streams, the
majority of time spent constructing `page_params` is spent marshalling
data on which users are subscribed to which streams, which is an area
of active optimization work.

### Fetching message history

Bulk requests for message content and metadata
([`GET /messages`](https://zulip.com/api/get-messages)) account for
~3% of total HTTP requests. The zulip web app has a few major reasons
it does a large number of these requests:

- Most of these requests are from users clicking into different views
  -- to avoid certain subtle bugs, Zulip's web app currently fetches
  content from the server even when it has the history for the
  relevant stream/topic cached locally.
- When a browser opens the Zulip web app, it will eventually fetch and
  cache in the browser all messages newer than the oldest unread
  message in a non-muted context. This can be in total extremely
  expensive for users with 10,000s of unread messages, resulting in a
  single browser doing 100 of these requests.
- When a new version of the Zulip server is deployed, every browser
  will reload within 30 minutes to ensure they are running the latest
  code. For installations that deploy often like chat.zulip.org and
  zulip.com, this can result in a thundering herd effect for both `/`
  and `GET /messages`. A great deal of care has been taking in
  designing this [auto-reload
  system](hashchange-system.md#server-initiated-reloads)
  to spread most of that herd over several minutes.

Typical requests consume 20-100ms to process, much of which is waiting
to fetch message IDs from the database and then their content from
memcached. While not large in an absolute sense, these requests are
expensive relative to most other Zulip endpoints.

Some requests, like full-text search for commonly used words, can be
more expensive, but they are sufficiently rare in an absolute sense so
as to be immaterial to the overall scalability of the system.

This server-side code path is already heavily optimized on a
per-request basis. However, we have technical designs for optimizing
the overall frequency with which clients need to make these requests
in two major ways:

- Improving [client-side
  caching](https://github.com/zulip/zulip/issues/15131) to allow
  caching of narrows that the user has viewed in the current session,
  avoiding repeat fetches of message content during a given session.
- Adjusting the behavior for clients with 10,000s of unread messages
  to not fetch as much old message history into the cache. See [this
  issue](https://github.com/zulip/zulip/issues/16697) for relevant
  design work.

Together, it is likely that these changes will reduce the total
scalability cost of fetching message history dramatically.

### User uploads

Requests to fetch uploaded files (including user avatars) account for
about 5% of total HTTP requests. Zulip spends consistently ~10-15ms
processing one of these requests (mostly authorization logic), before
handing off delivery of the file to `nginx` (which may itself fetch
from S3, depending on the configured [upload
backend](../production/upload-backends.md)).

### Sending and editing messages

[Sending new messages](sending-messages.md) (including
incoming webhooks) represents less than 0.5% of total request volume.
That this number is small should not be surprising even though sending
messages is intuitively the main feature of a chat service: a message
sent to 50 users triggers ~50 `GET /events` requests.

A typical message-send request takes 20-70ms, with more expensive
requests typically resulting from [Markdown
rendering](markdown.md) of more complex syntax. As a
result, these requests are not material to Zulip's scalability.
Editing messages and adding emoji reactions are very similar to
sending them for the purposes of performance and scalability, since
the same clients need to be notified, and these requests are lower in volume.

That said, we consider the performance of these endpoints to be some
of the most important for Zulip's user experience, since even with
local echo, these are some of the places where any request processing
latency is highly user-visible.

Typing notifications are slightly higher volume than sending messages,
but are also extremely cheap (~3ms).

### Other endpoints

Other API actions, like subscribing to a stream, editing settings,
registering an account, etc., are vanishingly rare compared to the
requests detailed above, fundamentally because almost nobody changes
these things more than a few dozen times over the lifetime of their
account, whereas everything above are things that a given user might
do thousands of times.

As a result, performance work on those requests is generally only
important for latency reasons, not for optimizing the overall
scalability of a Zulip server.

## Queue processors and cron jobs

The above doesn't cover all of the work that a production Zulip server
does; various tasks like sending outgoing emails or recording the data
that powers [/stats](https://zulip.com/help/analytics) are run by
[queue processors](queuing.md) and cron jobs, not in
response to incoming HTTP requests. In practice, all of these have
been written such that they are immaterial to total load and thus
architectural scalability, though we do from time to time need to do
operational work to add additional queue processors for particularly
high-traffic queues. For all of our queue processors, any
serialization requirements are at most per-user, and thus it would be
straightforward to shard by `user_id` or `realm_id` if required.

## Service scalability

In addition to the above, which just focuses on the total amount of
CPU work, it's also relevant to think about load on infrastructure
services (memcached, redis, rabbitmq, and most importantly postgres),
as well as queue processors (which might get backlogged).

In practice, efforts to make an individual endpoint faster will very
likely reduce the load on these services as well. But it is worth
considering that database time is a more precious resource than
Python/CPU time (being harder to scale horizontally).

Most optimizations to make an endpoint cheaper will start with
optimizing the database queries and/or employing
[caching](caching.md), and then continue as needed with
profiling of the Python code and any memcached queries.

For a handful of the critical code paths listed above, we further
optimize by skipping the Django ORM (which has substantial overhead)
for narrow sections; typically this is sufficient to result in the
database query time dominating that spent by the Python application
server process.

Zulip's [server logs](logging.md) are designed to
provide insight when a request consumes significant database or
memcached resources, which is useful both in development and in
production.
