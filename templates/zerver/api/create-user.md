# Create a user

{generate_api_description(/users:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users:post|example(admin_config=True)}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/users:post|example(admin_config=True)}

{tab|curl}

{generate_code_example(curl)|/users:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users:post}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users:post|fixture(200)}

A typical JSON response for when another user with the same
email address already exists in the realm:

{generate_code_example|/users:post|fixture(400)}
