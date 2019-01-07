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
["events" endpoint](/api/get-events-from-queue) to request events from
the Zulip server using long-polling.

The server will queue events for up to 10 minutes of inactivity.
After 10 minutes, your event queue will be garbage-collected.  The
server will send `heartbeat` events every minute, which makes it easy
to implement a robust client that does not miss events unless the
client loses network connectivity with the Zulip server for 10 minutes
or longer.

Once the server garbage-collects your event queue, the server will
[return an error](/api/get-events-from-queue#bad_event_queue_id-errors)
with a code of `BAD_EVENT_QUEUE_ID` if you try to fetch events from
the event queue.  Your software will need to handle that error
condition by re-initializing itself (e.g. this is what triggers your
browser reloading the Zulip webapp when your laptop comes back online
after being offline for more than 10 minutes).

When prototyping with this API, we recommend first calling `register`
with no `event_types` argument to see all the available data from all
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
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Register a queue
    const params = {
        event_types: ['message']
    };
    client.queues.register(params).then(console.log);
});

```

{tab|curl}

```
curl {{ api_url }}/v1/register \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
    -d 'event_types=["message"]'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/register:post}

## Response

#### Return values

* `queue_id`: The ID of the queue that has been allocated for your client.
* `last_event_id`: The initial value of `last_event_id` to pass to
  `GET /api/v1/events`.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/register:post|fixture(200)}
