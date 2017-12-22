# Private message

Send a private message to a user.

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
<li data-language="zulip-send">zulip-send</li>
<li data-language="javascript">JavaScript</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "type=private" \
    -d "to=hamlet@example.com" \
    -d "content=I come not, friends, to steal away your hearts."
```
</div>

<div data-language="python" markdown="1">
```python
#!/usr/bin/env python

import zulip
import sys

# Keyword arguments 'email' and 'api_key' are not required if you are using ~/.zuliprc
client = zulip.Client(email="othello-bot@example.com",
                      api_key="a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5",
                      site="{{ api_url }}")

# Send a private message
client.send_message({
    "type": "private",
    "to": "hamlet@example.com",
    "content": "I come not, friends, to steal away your hearts."
})

# Print each message the user receives
# This is a blocking call that will run forever
client.call_on_each_message(lambda msg: sys.stdout.write(str(msg) + "\n"))

# Print every event relevant to the user
# This is a blocking call that will run forever
# This will never be reached unless you comment out the previous line
client.call_on_each_event(lambda msg: sys.stdout.write(str(msg) + "\n"))
```
</div>

<div data-language="zulip-send" markdown="1"> You can use `zulip-send`
(available after you `pip install zulip`) to easily send Zulips from
the command-line, providing the message content via STDIN.

```bash
zulip-send hamlet@example.com \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

You can omit the `user` and `api-key` arguments if you have a `~/.zuliprc` file.

See also the [full API endpoint documentation.](/api/endpoints).
</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip');

const config = {
  username: 'othello-bot@example.com',
  apiKey: 'a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5',
  realm: '{{ api_url }}'
};

const client = zulip(config);

// Send a private message
client.messages.send({
  to: 'hamlet@example.com',
  type: 'private',
  content: 'I come not, friends, to steal away your hearts.'
});

// Register queue to receive messages for user
client.queues.register({
  event_types: ['message']
}).then((res) => {
  // Retrieve events from a queue
  // Blocking until there is an event (or the request times out)
  client.events.retrieve({
    queue_id: res.queue_id,
    last_event_id: -1,
    dont_block: false
  }).then(console.log);
});
```
</div>

</div>

</div>
