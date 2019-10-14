# Delete a user group

Delete a [user group](/help/user-groups).

`DELETE {{ api_url }}/v1/user_groups/{group_id}`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups/{group_id}:delete|example}

{tab|curl}

{generate_code_example(curl)|/user_groups/{group_id}:delete|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/user_groups/{group_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups/{group_id}:delete|fixture(200)}

An example JSON error response for an invalid user group id:

{generate_code_example|/user_groups/{group_id}:delete|fixture(400)}
