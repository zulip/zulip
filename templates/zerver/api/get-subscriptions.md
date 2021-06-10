{generate_api_title(/users/me/subscriptions:get)}

{generate_api_description(/users/me/subscriptions:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/users/me/subscriptions:get|example}

{tab|curl}

{generate_code_example(curl, include=[""])|/users/me/subscriptions:get|example}

You may pass the `include_subscribers` query parameter as follows:

{generate_code_example(curl)|/users/me/subscriptions:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:get}

## Response

{generate_return_values_table|zulip.yaml|/users/me/subscriptions:get}

#### Example response

{generate_code_example|/users/me/subscriptions:get|fixture(200)}

{generate_code_example|/users/me/subscriptions:get|fixture(400)}
