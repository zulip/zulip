# Add an emoji reaction

Add an [emoji reaction](/help/emoji-reactions) to a message.

`POST {{ api_url }}/v1/messages/{message_id}/reactions`


## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}/reactions:post|example}

{tab|curl}

{generate_code_example(curl, exclude=["emoji_code","reaction_type"])|/messages/{message_id}/reactions:post|example}

{end_tabs}

## Arguments


{generate_api_arguments_table|zulip.yaml|/messages/{message_id}/reactions:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}/reactions:post|fixture(200)}
