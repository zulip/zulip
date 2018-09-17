# Delete a message

Permanently delete a message.

`DELETE {{ api_url }}/v1/messages/<msg_id>`

This API corresponds to the
[delete a message completely][delete-completely] feature documented in
the Zulip Help Center.

[delete-completely]: /help/edit-or-delete-a-message#delete-a-message-completely

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}:delete|example(admin_config=True)}

{tab|curl}

```
curl -X DELETE {{ api_url }}/v1/messages/{message_id} \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}:delete|fixture(200)}

An example JSON response for when the specified message does not exist:

{generate_code_example|/messages/{message_id}:delete|fixture(400_invalid_message)}

An example JSON response for when the user making the query does not
have permission to delete the message:

{generate_code_example|/messages/{message_id}:delete|fixture(400_not_admin)}
