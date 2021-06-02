{generate_api_title(/users/me/subscriptions:post)}

{generate_api_description(/users/me/subscriptions:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:post|example}

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

{generate_return_values_table|zulip.yaml|/users/me/subscriptions:post}

#### Example response

{generate_code_example|/users/me/subscriptions:post|fixture(200)}

{generate_code_example|/users/me/subscriptions:post|fixture(400)}
