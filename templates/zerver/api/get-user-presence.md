# Get user presence

{generate_api_description(/users/{user_id_or_email}/presence:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{user_id_or_email}/presence:get|example}

{tab|curl}

{generate_code_example(curl)|/users/{user_id_or_email}/presence:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/{user_id_or_email}/presence:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/{user_id_or_email}/presence:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{user_id_or_email}/presence:get|fixture(200)}
