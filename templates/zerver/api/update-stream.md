# Update a stream

{generate_api_description(/streams/{stream_id}:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/streams/{stream_id}:patch|example}

{tab|curl}

{generate_code_example(curl, include=["new_name", "description", "is_private"])|/streams/{stream_id}:patch|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/streams/{stream_id}:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/streams/{stream_id}:patch|fixture(200)}

An example JSON response for when the supplied stream does not exist:

{generate_code_example|/streams/{stream_id}:patch|fixture(400)}
