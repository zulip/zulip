# Delete custom emoji

{generate_api_description(/realm/emoji/{emoji_name}:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/emoji/{emoji_name}:delete|example}

{tab|curl}

{generate_code_example(curl)|/realm/emoji/{emoji_name}:delete|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/realm/emoji/{emoji_name}:delete}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/realm/emoji/{emoji_name}:delete}


#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/emoji/{emoji_name}:delete|fixture(200)}
