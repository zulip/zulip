# Deactivate a user

{!api-admin-only.md!}

Deactivate a user. See [help](https://zulipchat.com/help/deactivate-or-reactivate-a-user).

`DELETE {{ api_url }}/v1/users/{user_id}`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{user_id}:delete|example}

{tab|curl}

{generate_code_example(curl)|/users/{user_id}:delete|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/{user_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{user_id}:delete|fixture(200)}

An example JSON error response when the user id of the only organization administrator is passed:

{generate_code_example|/users/{user_id}:delete|fixture(400)}
