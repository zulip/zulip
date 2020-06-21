# Get own user

{generate_api_description(/users/me:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/users/me:get|example}

{tab|curl}

{generate_code_example(curl)|/users/me:get|example}

{end_tabs}

## Parameters

This endpoint takes no parameters.

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/me:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me:get|fixture(200)}
