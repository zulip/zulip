# Delete a queue

Delete a previously registered queue.

`DELETE {{ api_url }}/v1/events`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/events:delete|example}

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
    const queueParams = {
        event_types: ['message']
    };
    client.queues.register(queueParams).then((res) => {
        // Delete a queue
        const deregisterParams = {
            queue_id: res.queue_id,
        };
        client.queues.deregister(deregisterParams).then(console.log);
    });
});

```

{tab|curl}

```
curl -X "DELETE" {{ api_url }}/v1/events \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
    -d 'queue_id=1515096410:1'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/events:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/events:delete|fixture(200)}

A typical JSON response for when the `queue_id` is non-existent or the
associated queue has already been deleted:

{generate_code_example|/events:delete|fixture(400)}
