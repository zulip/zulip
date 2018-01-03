# Private message

Send a private message to a user or multiple users.

`POST {{ api_url }}/v1/messages`

## Arguments

{generate_api_arguments_table|arguments.json|private-message.md}

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

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Send a private message
client.send_message({
    "type": "private",
    "to": "hamlet@example.com",
    "content": "I come not, friends, to steal away your hearts."
})

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

See also the [full API endpoint documentation](/api/endpoints).
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

// Send a private message
client.messages.send({
  to: 'hamlet@example.com',
  type: 'private',
  content: 'I come not, friends, to steal away your hearts.'
});

```
</div>

</div>

</div>

## Response

#### Return values

* `id`: The ID of the newly created message

#### Example response

{!successful-api-send-message-json-response.md!}

A typical failed JSON response for when the recipient's email
address is invalid:

```
{
    'code':'BAD_REQUEST',
    'msg':"Invalid email 'hamlet@example.com'",
    'result':'error'
}
```

{!invalid-api-key-json-response.md!}
