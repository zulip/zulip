# Subscribe to a stream

{generate_api_description(/users/me/subscriptions:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:post|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/users/me/subscriptions:post|example}

{tab|curl}

{generate_code_example(curl, include=["subscriptions"])|/users/me/subscriptions:post|example}

To subscribe another user to a stream, you may pass in
the `principals` parameter, like so:

{generate_code_example(curl, include=["subscriptions", "principals"])|/users/me/subscriptions:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:post}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/me/subscriptions:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions:post|fixture(200_0)}

A typical successful JSON response when the user is already subscribed to
the streams specified:

{generate_code_example|/users/me/subscriptions:post|fixture(200_1)}

A typical response for when the requesting user does not have access to
a private stream and `authorization_errors_fatal` is `True`:

{generate_code_example|/users/me/subscriptions:post|fixture(400_0)}


A typical response for when the requesting user does not have access to
a private stream and `authorization_errors_fatal` is `False`:

{generate_code_example|/users/me/subscriptions:post|fixture(400_1)}
