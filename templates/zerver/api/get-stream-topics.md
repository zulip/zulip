# Get topics in a stream

{generate_api_description(/users/me/{stream_id}/topics:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/{stream_id}/topics:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/users/me/{stream_id}/topics:get|example}

{tab|curl}

{generate_code_example(curl)|/users/me/{stream_id}/topics:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/{stream_id}/topics:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/me/{stream_id}/topics:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/{stream_id}/topics:get|fixture(200)}

An example JSON response for when the user is attempting to fetch the topics
of a non-existing stream (or also a private stream they don't have access to):

{generate_code_example|/users/me/{stream_id}/topics:get|fixture(400)}
