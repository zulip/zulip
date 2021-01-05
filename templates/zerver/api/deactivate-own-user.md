# Deactivate own user

{generate_api_description(/users/me:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me:delete|example}

{tab|curl}

{generate_code_example(curl)|/users/me:delete|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me:delete|fixture(200)}

An example JSON error response when attempting to deactivate the only
organization owner in an organization:

{generate_code_example|/users/me:delete|fixture(400)}
