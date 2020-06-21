# Delete a stream

{generate_api_description(/streams/{stream_id}:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/streams/{stream_id}:delete|example}

{tab|curl}

{generate_code_example(curl)|/streams/{stream_id}:delete|example}

{end_tabs}

## Parameters

**Note**: The following parameters are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/streams/{stream_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/streams/{stream_id}:delete|fixture(200)}

An example JSON response for when the supplied stream does not exist:

{generate_code_example|/streams/{stream_id}:delete|fixture(400)}
