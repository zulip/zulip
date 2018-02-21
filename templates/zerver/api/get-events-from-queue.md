# Get new events from an events queue

`GET {{ api_url }}/v1/events`

This endpoint allows you to receive new events from an event queue that
can be created by
[requesting the `{{ api_url}}/v1/register` endpoint](/api/register-queue).

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

# Print each message the user receives
# This is a blocking call that will run forever
client.call_on_each_message(lambda msg: sys.stdout.write(str(msg) + "\n"))

# Print every event relevant to the user
# This is a blocking call that will run forever
# This will never be reached unless you comment out the previous line
client.call_on_each_event(lambda msg: sys.stdout.write(str(msg) + "\n"))
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

{generate_api_arguments_table|arguments.json|get-events-from-queue.md}

**Note**: The arguments documented above are optional in the sense that
even if you haven't registered a queue by explicitly requesting the
`{{ api_url}}/v1/register` endpoint, you could pass the arguments for
[the `{{ api_url}}/v1/register` endpoint](/api/register-queue) to this
endpoint and a queue would be registered in the absence of a `queue_id`.

You may also pass in the following keyword arguments to `call_on_each_event`:

{generate_api_arguments_table|arguments.json|call_on_each_event}

## Response

#### Return values

* `events`: An array (possibly zero-length if `dont_block` is set) of events
  with IDs newer than `last_event_id`. Event IDs are guaranted to be increasing,
  but they are not guaranteed to be consecutive.

#### Example response

A typical successful JSON response may look like:

```
{
    'result':'success',
    'msg':'',
    'events':[
        {
            'type':'message',
            'id':0,
            'message':{
                'content_type':'text/x-markdown',
                'avatar_url':'https://url/for/othello-bots/avatar',
                'timestamp':1375978403,
                'display_recipient':'Denmark',
                'sender_id':13215,
                'sender_full_name':'Othello Bot',
                'sender_email':'othello-bot@example.com',
                'sender_short_name':'othello-bot',
                'sender_realm_str':'example',
                'content':'Something is rotten in the state of Denmark.',
                'recipient_id':12314,
                'client':'website',
                'subject_links':[

                ],
                'subject':'Castle',
                'type':'stream',
                'id':12345678,

            }
        },
        {
            'type':'message',
            'id':1,
            'message':{
                'content_type':'text/x-markdown',
                'avatar_url':'https://url/for/othello-bots/avatar',
                'timestamp':1375978404,
                'display_recipient':[
                    {
                        'full_name':'Hamlet of Denmark',
                        'email':'hamlet@example.com',
                        'short_name':'hamlet',
                        'id':31572
                    }
                ],
                'sender_id':13215,
                'sender_full_name':'Othello Bot',
                'sender_email':'othello-bot@example.com',
                'sender_short_name':'othello-bot',
                'sender_realm_str':'example',
                'content':'I come not, friends, to steal away your hearts.',
                'recipient_id':18391,
                'client':'website',
                'subject_links':[

                ],
                'subject':'',
                'type':'private',
                'id':12345679,

            }
        }
    ]
}
```
