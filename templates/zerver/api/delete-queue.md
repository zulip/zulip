# Delete an event queue

{generate_api_description(/events:delete)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/events:delete|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/events:delete|example}

{tab|curl}

{generate_code_example(curl)|/events:delete|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/events:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/events:delete|fixture(200)}

A typical JSON response for when the `queue_id` is non-existent or the
associated queue has already been deleted:

{generate_code_example|/events:delete|fixture(400)}
