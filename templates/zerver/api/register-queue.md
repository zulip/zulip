# Register an event queue

`POST {{ api_url }}/v1/register`

This powerful endpoint can be used to register a Zulip "event queue"
(subscribed to certain types of "events", or updates to the messages
and other Zulip data the current user has access to), as well as to
fetch the current state of that data.

(`register` also powers the `call_on_each_event` Python API, and is
intended primarily for complex applications for which the more convenient
`call_on_each_event` API is insufficient).

This endpoint returns a `queue_id` and a `last_event_id`; these can be
used in subsequent calls to the
["events" endpoint](/api/get-events) to request events from
the Zulip server using long-polling.

The server will queue events for up to 10 minutes of inactivity.
After 10 minutes, your event queue will be garbage-collected.  The
server will send `heartbeat` events every minute, which makes it easy
to implement a robust client that does not miss events unless the
client loses network connectivity with the Zulip server for 10 minutes
or longer.

Once the server garbage-collects your event queue, the server will
[return an error](/api/get-events#bad_event_queue_id-errors)
with a code of `BAD_EVENT_QUEUE_ID` if you try to fetch events from
the event queue.  Your software will need to handle that error
condition by re-initializing itself (e.g. this is what triggers your
browser reloading the Zulip webapp when your laptop comes back online
after being offline for more than 10 minutes).

When prototyping with this API, we recommend first calling `register`
with no `event_types` parameter to see all the available data from all
supported event types.  Before using your client in production, you
should set appropriate `event_types` and `fetch_event_types` filters
so that your client only requests the data it needs.  A few minutes
doing this often saves 90% of the total bandwidth and other resources
consumed by a client using this API.

See the
[events system developer documentation](https://zulip.readthedocs.io/en/latest/subsystems/events-system.html)
if you need deeper details about how the Zulip event queue system
works, avoids clients needing to worry about large classes of
potentially messy races, etc.

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/register:post|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/register:post|example}

{tab|curl}

{generate_code_example(curl, include=["event_types"])|/register:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/register:post}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/register:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/register:post|fixture(200)}
