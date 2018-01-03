# Register a queue

Register a queue to receive new messages.

(This endpoint is used internally by the API, and it is
documented here for advanced users that want to customize
how they register for Zulip events.  The queue_id returned
from this endpoint can be used in a subsequent call to the
"events" endpoint.)

`POST {{ api_url }}/v1/register`

## Arguments

{generate_api_arguments_table|arguments.json|register-queue.md}

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
<li data-language="javascript">JavaScript</li>
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

```
#!/usr/bin/env python

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Register the queue
print(client.register())

# You may pass in one or more of the above arguments as keyword
# arguments, like so:
print(client.register(
    event_types=['messages']
))
```

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

const config = {
  username: 'othello-bot@example.com',
  apiKey: 'a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5',
  realm: '{{ api_url }}'
};

const client = zulip(config);

// Register a queue
const params = {
    event_types: ['message']
};

client.queues.register(params).then(res => {
    console.log(res);
});

```
</div>

</div>

</div>

## Response

#### Return values

* `queue_id`: The ID of the queue that has been allocated for your client.
* `last_event_id`: The initial value of `last_event_id` to pass to
  `GET /api/v1/events`.

#### Example response

A typical successful JSON response may look like:

```
{
    'last_event_id':-1,
    'queue_id':'1514938867:1',
    'result':'success',
    'msg':''
}
```

{!invalid-api-key-json-response.md!}
