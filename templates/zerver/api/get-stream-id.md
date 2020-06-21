# Get stream ID

{generate_api_description(/get_stream_id:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/get_stream_id:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/get_stream_id:get|example}

{tab|curl}

{generate_code_example(curl)|/get_stream_id:get|example}

{end_tabs}

## Parameters

**Note**: The following parameters are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/get_stream_id:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/get_stream_id:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/get_stream_id:get|fixture(200)}

An example JSON response for when the supplied stream does not exist:

{generate_code_example|/get_stream_id:get|fixture(400)}
