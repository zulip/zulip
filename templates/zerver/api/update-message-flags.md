{generate_api_title(/messages/flags:post)}

{generate_api_description(/messages/flags:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/flags:post|example}

{generate_code_example(javascript)|/messages/flags:post|example}

{tab|curl}

{generate_code_example(curl)|/messages/flags:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/messages/flags:post}

## Available flags
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
                <td><code>read</code></td>
                <td>
                    Whether the user has read the message.  Messages
                    start out unread (except for messages the user
                    themself sent using a non-API client) and can
                    later be marked as read.
                </td>
            </tr>
            <tr>
                <td><code>starred</code></td>
                <td>Whether the user has <a href="/help/star-a-message">starred this message</a>.</td>
            </tr>
            <tr>
                <td><code>collapsed</code></td>
                <td>Whether the user has <a href="/help/collapse-a-message">collapsed this message</a>.</td>
            </tr>
            <tr>
                <td><code>mentioned</code></td>
                <td>
                    Whether the current user
                    <a href="/help/mention-a-user-or-group">was mentioned</a>
                    by this message, either directly or via a user
                    group. Cannot be changed by the user directly, but
                    can change if the message is edited to add/remove
                    a mention of the current user.
                </td>
            </tr>
            <tr>
                <td><code>wildcard_mentioned</code></td>
                <td>
                    Whether this message contained
                    <a href="/help/mention-a-user-or-group#mention-everyone-on-a-stream">wildcard mention</a>
                    like @**all**. Cannot be changed by the user directly, but
                    can change if the message is edited to add/remove
                    a wildcard mention.
                </td>
            </tr>
            <tr>
                <td><code>has_alert_word</code></td>
                <td>
                    Whether the message contains any of the current user's
                    <a href="/help/add-an-alert-word">configured alert words</a>.
                    Cannot be changed by the user directly, but
                    can change if the message is edited to add/remove
                    one of the current user's alert words.
                </td>
            </tr>
            <tr>
                <td><code>historical</code></td>
                <td>
                    True for messages that the user did not receive
                    at the time they were sent but later was added to
                    the user's history (E.g. because they starred or
                    reacted to a message sent to a public stream
                    before they subscribed to that stream). Cannot be
                    changed by the user directly.
                </td>
            </tr>
        </tbody>
    </table>
</div>
{generate_parameter_description(/messages/flags:post)}

## Response

{generate_return_values_table|zulip.yaml|/messages/flags:post}

#### Example response

{generate_code_example|/messages/flags:post|fixture(200)}

{generate_code_example|/messages/flags:post|fixture(400)}
