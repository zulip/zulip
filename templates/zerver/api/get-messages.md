{generate_api_title(/messages:get)}

{generate_api_description(/messages:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages:get|example}

{generate_code_example(javascript)|/messages:get|example}

{tab|curl}

{generate_code_example(curl)|/messages:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/messages:get}

{generate_parameter_description(/messages:get)}

## Response

When a request is successful, this endpoint returns a dictionary
containing the following (in addition to the `msg` and `result` keys
present in all Zulip API responses).

{generate_return_values_table|zulip.yaml|/messages:get}

#### Example response

{generate_code_example|/messages:get|fixture(200)}

{generate_code_example|/messages:get|fixture(400)}
