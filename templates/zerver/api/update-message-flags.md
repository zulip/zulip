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

{generate_code_example(curl)|/messages/flags:post|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/flags:post}

## Available Flags
<div>
    <table>
        <thead>
            <tr>
                <th style="width:30%">Flag</th>
                <th style="width:70%">Purpose</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>`read`</td>
                <td>
                    Whether the user has read the message.  Messages
                    start out unread (except for messages the user
                    themself sent using a non-API client) and can
                    later be marked as read.
                </td>
            </tr>
            <tr>
                <td>`starred`</td>
                <td>Whether the user has [starred this message](/help/star-a-message).</td>
            </tr>
            <tr>
                <td>`collapsed`</td>
                <td>Whether the user has [collapsed this message](/help/collapse-a-message).</td>
            </tr>
            <tr>
                <td>`mentioned`</td>
                <td>
                     Whether the current user [was
                     mentioned](/help/mention-a-user-or-group) by
                     this message, either directly or via a user
                     group.  Not editable.
                </td>
            </tr>
            <tr>
                <td>`wildcard_mentioned`</td>
                <td>
                     Whether this message contained [wildcard
                     mention](/help/mention-a-user-or-group#mention-everyone-on-a-stream)
                     like @**all**.  Not editable.
                </td>
            </tr>
            <tr>
                <td>`has_alert_word`</td>
                <td>
                     Whether the message contains any of the current
                     user's [configured alert
                     words](/help/add-an-alert-word).  Not editable.
                </td>
            </tr>
            <tr>
                <td>`historical`</td>
                <td>
                     True for messages that the user did not receive
                     at the time they were sent but later was added to
                     the user's history (E.g. because they starred or
                     reacted to a message sent to a public stream
                     before they subscribed to that stream).  Not
                     editable.
                </td>
            </tr>
        </tbody>
    </table>
</div>

## Response

#### Return values

* `messages`: An array with the IDs of the modified messages.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/flags:post|fixture(200)}
