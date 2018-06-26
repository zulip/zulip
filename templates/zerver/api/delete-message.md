# Delete a message

Delete a message.

`DELETE {{ api_url }}/v1/messages/<msg_id>`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl -X DELETE {{ api_url }}/v1/messages/{message_id} \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/messages/{message_id}:delete|example(admin_config=True)}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}:delete|fixture(200)}

An example JSON response for when the specified message does not exist:

{generate_code_example|/messages/{message_id}:delete|fixture(400_invalid_message)}

An example JSON response for when the user making the query is not an
administrator:

{generate_code_example|/messages/{message_id}:delete|fixture(400_not_admin)}
