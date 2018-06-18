# Send a message

Send a stream or a private message.

`POST {{ api_url }}/v1/messages`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="javascript">JavaScript</li>
<li data-language="curl">curl</li>
<li data-language="zulip-send">zulip-send</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
# For stream messages
curl {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "type=stream" \
    -d "to=Denmark" \
    -d "subject=Castle" \
    -d "content=Something is rotten in the state of Denmark."

# For private messages
curl {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "type=private" \
    -d "to=hamlet@example.com" \
    -d "content=I come not, friends, to steal away your hearts."
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|send-message|example}

</div>

<div data-language="zulip-send" markdown="1"> You can use `zulip-send`
(available after you `pip install zulip`) to easily send Zulips from
the command-line, providing the message content via STDIN.

```bash
# For stream messages
zulip-send --stream Denmark --subject Castle \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5

# For private messages
zulip-send hamlet@example.com \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

#### Passing in the message on the command-line

If you'd like, you can also provide the message on the command-line with the
`-m` or `--message` flag, as follows:


```bash
zulip-send --stream Denmark --subject Castle \
    --message "Something is rotten in the state of Denmark." \
    --user othello-bot@example.com --api-key a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5
```

You can omit the `user` and `api-key` arguments if you have a `~/.zuliprc`
file.

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Download zuliprc-dev from your dev server
const config = {
    zuliprc: 'zuliprc-dev',
};

// Send a stream message
zulip(config).then((client) => {
    // Send a message
    const params = {
        to: 'Denmark',
        type: 'stream',
        subject: 'Castle',
        content: 'Something is rotten in the state of Denmark.'
    }

    client.messages.send(params).then(console.log);
});

// Send a private message
zulip(config).then((client) => {
    // Send a private message
    const params = {
        to: 'hamlet@example.com',
        type: 'private',
        content: 'I come not, friends, to steal away your hearts.',
    }

    client.messages.send(params).then(console.log);
});

```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|send-message.md}

## Response

#### Return values

* `id`: The ID of the newly created message

#### Example response
A typical successful JSON response may look like:

{generate_code_example|send-message|fixture}

A typical failed JSON response for when a stream message is sent to a stream
that does not exist:

{generate_code_example|nonexistent-stream-error|fixture}

A typical failed JSON response for when a private message is sent to a user
that does not exist:

{generate_code_example|invalid-pm-recipient-error|fixture}
