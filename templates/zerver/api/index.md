# We hear you like APIs...

We have a [well-documented API](/api/endpoints) that allows you to build custom integrations, in addition to our [existing integrations](/integrations). For ease-of-use, we've created a Python module that you can drop in to a project to start interacting with our API. There is also a [JavaScript library](https://github.com/zulip/zulip-js) that can be used either in the browser or in Node.js.

**Don't want to make it yourself?** Zulip [already integrates with lots of services](/integrations).

### Installation instructions
#### Python Installation
Install it with [pip](https://pypi.python.org/pypi/zulip/):
```
pip install zulip
```
#### JavaScript Installation
Install it with [npm](https://www.npmjs.com/package/zulip-js):
```
npm install zulip-js
```

### Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
<li data-language="zulip-send">zulip-send</li>
<li data-language="javascript">JavaScript</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">
No download required!

#### Stream message

```
curl {{ external_api_uri_subdomain }}/v1/messages \
-u BOT_EMAIL_ADDRESS:BOT_API_KEY \
-d "type=stream" \
-d "to=Denmark" \
-d "subject=Castle" \
-d "content=Something is rotten in the state of Denmark."
```

#### Private message
```
curl {{ external_api_uri_subdomain }}/v1/messages \
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
          site="{{ external_api_uri_subdomain }}")
# Send a stream message
client.send_message({
"type": "stream",
"to": "Denmark",
"subject": "Castle",
"content": "Something is rotten in the state of Denmark."
})
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

<div data-language="zulip-send" markdown="1">
You can use `zulip-send` (found in `bin/` in the tarball) to easily send Zulips from the command-line, providing the message to be sent on STDIN.

#### Stream message

```bash
zulip-send --stream Denmark --subject Castle \
--user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

#### Private message

```bash
zulip-send hamlet@example.com \
--user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

#### Passing in the message on the command-line

If you'd like, you can also provide the message on the command-line with the `-m` flag, as follows:


```bash
zulip-send --stream Denmark --subject Castle \
-m "Something is rotten in the state of Denmark." \
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
realm: '{{ external_api_uri_subdomain }}'
};

const client = zulip(config);

// Send a message
client.messages.send({
to: 'Denmark',
type: 'stream',
subject: 'Castle',
content: 'Something is rotten in the state of Denmark.'
});

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


### API keys

You can create bots on your [settings page](/#settings).
Once you have a bot, you can use its email and API key to send messages.</p>

Create a bot:
<img class="screenshot" src="/static/images/api/create-bot.png" />

Look for the bot's email and API key:
<img class="screenshot" src="/static/images/api/bot-key.png" />

If you prefer to send messages as your own user, you can also find your API key on your [settings page](/#settings).
When using our python bindings, you may either specify the user
and API key for each Client object that you initialize, or let the binding look for
them in your `~/.zuliprc`, the default config file, which you can create as follows:

```
[api]
key=BOT_API_KEY
email=BOT_EMAIL_ADDRESS
```

Additionally, you can also specify the parameters as environment variables as follows:

```
export ZULIP_CONFIG=/path/to/zulipconfig
export ZULIP_EMAIL=BOT_EMAIL_ADDRESS
export ZULIP_API_KEY=BOT_API_KEY
```

The parameters specified in environment variables would override the parameters provided in the config file. For example, if you specify the variable `key` in the config file and specify `ZULIP_API_KEY` as an environment variable, the value of `ZULIP_API_KEY` would be considered.

The following variables can be specified:

1. `ZULIP_CONFIG`
2. `ZULIP_API_KEY`
3. `ZULIP_EMAIL`
4. `ZULIP_SITE`
5. `ZULIP_CERT`
6. `ZULIP_CERT_KEY`
7. `ZULIP_CERT_BUNDLE`
