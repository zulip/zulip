# Unsubscribe from a stream

{generate_api_description(/users/me/subscriptions:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:delete|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/users/me/subscriptions:delete|example}

{tab|curl}

{generate_code_example(curl, include=["subscriptions"])|/users/me/subscriptions:delete|example}

You may specify the `principals` parameter like so:

{generate_code_example(curl)|/users/me/subscriptions:delete|example}

**Note**: Unsubscribing another user from a stream requires
administrative privileges.

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:delete}

#### Return values

{generate_return_values_table|zulip.yaml|/users/me/subscriptions:delete}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions:delete|fixture(200)}

A typical failed JSON response for when the target stream does not exist:

{generate_code_example|/users/me/subscriptions:delete|fixture(400)}
