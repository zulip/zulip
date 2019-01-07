# Update a message's flags

Add or remove flags in a list of messages.

`POST {{ api_url }}/v1/messages/flags`

For updating the `read` flag on common collections of messages, see also
the
[special endpoints for marking message as read in bulk](/api/mark-as-read-bulk).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/flags:post|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

const flagParams = {
    messages: [4, 8, 15],
    flag: 'read',
};

zulip(config).then((client) => {
    // Add the "read" flag to messages with IDs 4, 8 and 15
    client.messages.flags.add(flagParams)
    .then(console.log)

    // Remove the "read" flag from said messages
    client.messages.flags.remove(flagParams)
    .then(console.log);
});
```

{tab|curl}

```
curl -X POST {{ api_url }}/v1/messages/flags \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "messages=[4,8,15]" \
    -d "op=add" \
    -d "flag=starred"
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/flags:post}

## Response

#### Return values

* `messages`: An array with the IDs of the modified messages.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/flags:post|fixture(200)}
