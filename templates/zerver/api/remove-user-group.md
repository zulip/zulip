# Delete a user group

{generate_api_description(/user_groups/{user_group_id}:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups/{user_group_id}:delete|example}

{tab|curl}

{generate_code_example(curl)|/user_groups/{user_group_id}:delete|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/user_groups/{user_group_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups/{user_group_id}:delete|fixture(200)}

An example JSON error response for an invalid user group id:

{generate_code_example|/user_groups/{user_group_id}:delete|fixture(400)}
