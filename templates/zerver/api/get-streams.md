{generate_api_title(/streams:get)}

{generate_api_description(/streams:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/streams:get|example}

{generate_code_example(javascript)|/streams:get|example}

{tab|curl}

{generate_code_example(curl)|/streams:get|example}

You may pass in one or more of the parameters mentioned above
as URL query parameters, like so:

{generate_code_example(curl, include=["include_public"])|/streams:get|example}

{end_tabs}

## Parameters

**Note**: The following parameters are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/streams:get}

## Response

{generate_return_values_table|zulip.yaml|/streams:get}

#### Example response

{generate_code_example|/streams:get|fixture(200)}

{generate_code_example|/streams:get|fixture(400)}
