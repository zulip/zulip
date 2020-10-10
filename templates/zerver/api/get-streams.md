# Get all streams

{generate_api_description(/streams:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/streams:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/streams:get|example}

{tab|curl}

{generate_code_example(curl, include=[""])|/streams:get|example}

You may pass in one or more of the parameters mentioned above
as URL query parameters, like so:

{generate_code_example(curl, include=["include_public"])|/streams:get|example}

{end_tabs}

## Parameters

**Note**: The following parameters are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/streams:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/streams:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/streams:get|fixture(200)}

An example JSON response for when the user is not authorized to use the
`include_all_active` parameter (i.e. because they are not an organization
administrator):

{generate_code_example|/streams:get|fixture(400)}
