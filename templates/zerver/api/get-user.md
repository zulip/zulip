# Get a user

{generate_api_description(/users/{user_id}:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/{user_id}:get|example}

{tab|curl}

{generate_code_example(curl, include=[""])|/users/{user_id}:get|example}

You may pass the `client_gravatar` or `include_custom_profile_fields` query parameter as follows:

{generate_code_example(curl)|/users/{user_id}:get|example}

{end_tabs}

## Parameters

**Note**: The following parameters are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/users/{user_id}:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml}|/users/{user_id}:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{user_id}:get|fixture(200)}
