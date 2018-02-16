# Register a queue

Register a queue to receive new messages.

(This endpoint is used internally by the API, and it is
documented here for advanced users that want to customize
how they register for Zulip events.  The `queue_id` returned
from this endpoint can be used in a subsequent call to the
["events" endpoint](/api/get-events-from-queue).)

`POST {{ api_url }}/v1/register`

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
curl {{ api_url }}/v1/register \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
    -d 'event_types=["message"]'
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|register-queue|example}

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
    const params = {
        event_types: ['message']
    };
    client.queues.register(params).then(console.log);
});

```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|register-queue.md}

## Response

#### Return values

* `queue_id`: The ID of the queue that has been allocated for your client.
* `last_event_id`: The initial value of `last_event_id` to pass to
  `GET /api/v1/events`.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|register-queue|fixture}
