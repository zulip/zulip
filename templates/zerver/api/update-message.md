# Update a message

Edit/update the content or topic of a message.

`PATCH {{ api_url }}/v1/messages/<msg_id>`

`<msg_id>` in the above URL should be replaced with the ID of the
message you wish you update.

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
curl -X "PATCH" {{ api_url }}/v1/messages/<msg_id> \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "content=New content"
```
</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|update-message|example}

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
    // Update a message
    const params = {
        message_id: 131,
        content: 'New Content',
    }

    client.messages.update(params).then(console.log);
});
```
</div>

</div>

</div>

## Permissions

You only have permission to edit a message if:

1. You sent it, **OR**:
2. This is a topic-only edit for a (no topic) message, **OR**:
3. This is a topic-only edit and you are an admin.

## Arguments

{generate_api_arguments_table|arguments.json|update-message.md}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|update-message|fixture}

A typical JSON response for when one doesn't have the permission to
edit a particular message:

{generate_code_example|update-message-edit-permission-error|fixture}
