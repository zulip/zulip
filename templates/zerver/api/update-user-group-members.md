# Update user group members

{generate_api_description(/user_groups/{user_group_id}/members:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups/{user_group_id}/members:post|example}

{tab|curl}

{generate_code_example(curl, exclude=["delete"])|/user_groups/{user_group_id}/members:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/user_groups/{user_group_id}/members:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups/{user_group_id}/members:post|fixture(200)}
