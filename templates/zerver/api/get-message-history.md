# Get a message's edit history

{generate_api_description(/messages/{message_id}/history:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}/history:get|example}

{tab|curl}

{generate_code_example(curl)|/messages/{message_id}/history:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}/history:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/messages/{message_id}/history:get}

Please note that the original message's snapshot only contains the fields
`topic`, `content`, `rendered_content`, `timestamp` and `user_id`. This
snapshot will be the only one present if the message has never been edited.

Also note that if a message's content was edited (but not the topic)
or the topic was edited (but not the content), the snapshot object
will only contain data for the modified fields (e.g. if only the topic
was edited, `prev_content`, `prev_rendered_content`, and
`content_html_diff` will not appear).

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}/history:get|fixture(200)}

An example JSON response for when the specified message does not exist:

{generate_code_example|/messages/{message_id}/history:get|fixture(400)}
