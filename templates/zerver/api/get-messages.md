# Get messages

{generate_api_description(/messages:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/messages:get|example}

{tab|curl}

{generate_code_example(curl, exclude=["client_gravatar", "apply_markdown", "use_first_unread_anchor"])|/messages:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/messages:get}

## Response

#### Return values

When a request is successful, this endpoint returns a dictionary
containing the following (in addition to the `msg` and `result` keys
present in all Zulip API responses).

{generate_return_values_table|zulip.yaml|/messages:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages:get|fixture(200)}

[status-messages]: /help/format-your-message-using-markdown#status-messages
[linkification-filters]: /help/add-a-custom-linkification-filter
[message-flags]: /api/update-message-flags#available-flags
