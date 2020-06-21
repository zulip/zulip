# Update personal message flags

{generate_api_description(/messages/flags:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/flags:post|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/messages/flags:post|example}

{tab|curl}

{generate_code_example(curl)|/messages/flags:post|example}

{end_tabs}

## Parameters

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

{generate_return_values_table|zulip.yaml|/messages/flags:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/flags:post|fixture(200)}
