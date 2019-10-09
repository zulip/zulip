# Add emoji reaction to message

Add an emoji reaction to a message.

`POST {{ api_url }}/v1/messages/{message_id}reactions`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}/reactions:post|example}



{tab|curl}

``` curl
curl -X POST {{ api_url }}/v1/messages/{message_id}reactions \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "emoji_name=working_on_it"

```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/render:post}

## Response

#### Return values

* `rendered`: The rendered HTML.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/render:post|fixture(200)}
