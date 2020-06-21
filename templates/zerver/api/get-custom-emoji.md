# Get all custom emoji

{generate_api_description(/realm/emoji:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/emoji:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/realm/emoji:get|example}

{tab|curl}

{generate_code_example(curl)|/realm/emoji:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/realm/emoji:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/realm/emoji:get}


#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/emoji:get|fixture(200)}
