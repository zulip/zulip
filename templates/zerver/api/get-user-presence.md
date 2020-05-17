# Get user presence

{generate_api_description(/users/{email_or_id}/presence:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{email_or_id}/presence:get|example}

{tab|curl}

{generate_code_example(curl)|/users/{email_or_id}/presence:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/{email_or_id}/presence:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/{email_or_id}/presence:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{email_or_id}/presence:get|fixture(200)}
