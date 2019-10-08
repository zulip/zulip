# Get a raw message

Get the raw content of a message.

`GET {{ api_url }}/v1/messages/<msg_id>`

This is a rarely-used endpoint relevant for clients that primarily
work with HTML-rendered messages but might need to occasionally fetch
the message's raw markdown (e.g. for pre-filling a message-editing
UI).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}:get|example}

{tab|curl}

```
curl {{ api_url }}/v1/messages/<msg_id> \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}:get}

## Response

#### Return values

* `raw_content`: The raw content of the message.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}:get|fixture(200)}

An example JSON response for when the specified message does not exist or it
is not visible to the user making the query (e.g. it was a PM between other
two users):

{generate_code_example|/messages/{message_id}:get|fixture(400)}
