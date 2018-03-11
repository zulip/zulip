# Delete a queue

Delete a previously registered queue.

`DELETE {{ api_url }}/v1/events`

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
curl -X "DELETE" {{ api_url }}/v1/events \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
    -d 'queue_id=1515096410:1'
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|delete-queue|example}

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
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|delete-queue.md}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|delete-queue|fixture(successful_response)}

A typical JSON response for when the `queue_id` is non-existent or the
associated queue has already been deleted:

{generate_code_example|delete-queue|fixture(bad_event_queue_id_error)}
