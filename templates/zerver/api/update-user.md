# Update User

{!api-admin-only.md!}

Administrative endpoint to update the details of another user in the organization.

`PATCH {{ api_url }}/v1/users/{user_id}`

Supports everything an administrator can do to edit details of another
user's account, including editing full name,
[role](/help/roles-and-permissions), and [custom profile
fields](/help/add-custom-profile-fields).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{user_id}:patch|example}

{tab|curl}

{generate_code_example(curl)|/users/{user_id}:patch|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/{user_id}:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{user_id}:patch|fixture(200)}

A typical unsuccessful JSON response:

{generate_code_example|/users/{user_id}:patch|fixture(400)}
