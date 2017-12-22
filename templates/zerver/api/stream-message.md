# Stream message

Send a message to a stream.

`POST {{ api_url }}/v1/messages`

## Arguments

| Argument        | Example           | Required  | Description                 |
| --------------- | ----------------- | --------- | --------------------------- |
| `type`          | `stream`          | Required  | The type of message to be   |
|                 |                   |           | sent. `stream` for a stream |
|                 |                   |           | message and `private` for a |
|                 |                   |           | [private message][1].       |
|                 |                   |           |                             |
| `to`            | `Denmark`         | Required  | A string identifying the    |
|                 |                   |           | stream.                     |
|                 |                   |           |                             |
| `subject`       | `Castle`          | Optional  | The topic of the message.   |
|                 |                   |           | Only required if `type` is  |
|                 |                   |           | `stream`. Defaults to       |
|                 |                   |           | `None`. Maximum length of   |
|                 |                   |           | 60 characters.              |
|                 |                   |           |                             |
| `content`       | `Hello`           | Required  | The content of the message. |
|                 |                   |           | Maximum message size of     |
|                 |                   |           | 10000 bytes.                |

[1]: /api/private-message

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
    -d "type=stream" \
    -d "to=Denmark" \
    -d "subject=Castle" \
    -d "content=Something is rotten in the state of Denmark."
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

# Send a stream message
client.send_message({
    "type": "stream",
    "to": "Denmark",
    "subject": "Castle",
    "content": "Something is rotten in the state of Denmark."
})

```
</div>

<div data-language="zulip-send" markdown="1"> You can use `zulip-send`
(available after you `pip install zulip`) to easily send Zulips from
the command-line, providing the message content via STDIN.

```bash
zulip-send --stream Denmark --subject Castle \
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

See also the [full API endpoint documentation](/api/endpoints).
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

// Send a message
client.messages.send({
  to: 'Denmark',
  type: 'stream',
  subject: 'Castle',
  content: 'Something is rotten in the state of Denmark.'
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

A typical failed JSON response for when the target stream does not exist:

```
{
    'code':'BAD_REQUEST',
    'msg':"Stream 'Denmarkk' does not exist",
    'result':'error'
}
```

{!invalid-api-key-json-response.md!}
