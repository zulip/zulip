# Get events from an event queue

`GET {{ api_url }}/v1/events`

This endpoint allows you to receive new events from
[a registered event queue](/api/register-queue).

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="javascript">JavaScript</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl -G {{ api_url }}/v1/events \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
    -d "queue_id=1375801870:2942" \
    -d "last_event_id=-1"
```

</div>

<div data-language="python" markdown="1">

```
#!/usr/bin/env python

import sys
import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# If you already have a queue registered and thus, have a queue_id
# on hand, you may use client.get_events() and pass in the above
# arguments, like so:
print(client.get_events(
    queue_id="1515010080:4",
    last_event_id=-1
))
```

`call_on_each_message` and `call_on_each_event` will automatically register
a queue for you.

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Download zuliprc-dev from your dev server
const config = {
    zuliprc: 'zuliprc-dev',
};

zulip(config).then((client) => {
    // Register queue to receive messages for user
    const queueParams = {
        event_types: ['message']
    };
    client.queues.register(queueParams).then((res) => {
        // Retrieve events from a queue
        // Blocking until there is an event (or the request times out)
        const eventParams = {
            queue_id: res.queue_id,
            last_event_id: -1,
            dont_block: false,
        };
        client.events.retrieve(eventParams).then(console.log);
    });
});
```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/events:get}

**Note**: The arguments documented above are optional in the sense that
even if you haven't registered a queue by explicitly requesting the
`{{ api_url}}/v1/register` endpoint, you could pass the arguments for
[the `{{ api_url}}/v1/register` endpoint](/api/register-queue) to this
endpoint and a queue would be registered in the absence of a `queue_id`.

## Response

#### Return values

* `events`: An array (possibly zero-length if `dont_block` is set) of events
  with IDs newer than `last_event_id`. Event IDs are guaranted to be increasing,
  but they are not guaranteed to be consecutive.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/events:get|fixture(200)}

#### BAD_EVENT_QUEUE_ID errors

If the target event queue has been garbage collected, you'll get the
following error response:

{generate_code_example|/events:get|fixture(400)}

A compliant client will handle this error by re-initializing itself
(e.g. a Zulip webapp browser window will reload in this case).

See [the /register endpoint docs](/api/register-queue) for details on how to
handle these correctly.
