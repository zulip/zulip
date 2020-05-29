# Update a user

{generate_api_description(/users/{user_id}:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{user_id}:patch|example}

{tab|curl}

{generate_code_example(curl)|/users/{user_id}:patch|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/{user_id}:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{user_id}:patch|fixture(200)}

A typical unsuccessful JSON response:

{generate_code_example|/users/{user_id}:patch|fixture(400)}
