# Create a user group

{generate_api_description(/user_groups/create:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups/create:post|example}

{tab|curl}

{generate_code_example(curl)|/user_groups/create:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/user_groups/create:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups/create:post|fixture(200)}

An example JSON error response for when the one of the users does not exist:

{generate_code_example|/user_groups/create:post|fixture(400)}
