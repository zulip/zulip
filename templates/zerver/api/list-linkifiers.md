# List linkifiers

{generate_api_description(/realm/filters:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/filters:get|example}

{tab|curl}

{generate_code_example(curl)|/realm/filters:get|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/realm/filters:get}

## Response

#### Return values

* `filters`: An array of tuples, each representing one of the
  linkifiers set up in the organization. Each of these tuples contain the
  pattern, the formatted URL and the filter's ID, in that order. See
  the [Create linkifiers](/api/add-linkifiers) article for details on what
  each field means.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/filters:get|fixture(200)}
