# Unmute a user

{generate_api_description(/users/me/muted_users/{muted_user_id}:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/muted_users/{muted_user_id}:delete|example}

{tab|curl}

{generate_code_example(curl)|/users/me/muted_users/{muted_user_id}:delete|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/muted_users/{muted_user_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/muted_users/{muted_user_id}:delete|fixture(200)}

An example JSON response for when the user is nonexistent or inaccessible:

{generate_code_example|/users/me/muted_users/{muted_user_id}:delete|fixture(400_0)}

An example JSON response for when the user is not previously muted:

{generate_code_example|/users/me/muted_users/{muted_user_id}:delete|fixture(400_1)}
