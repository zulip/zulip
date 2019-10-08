# List linkifiers

List all of an organization's configured
[linkifiers](/help/add-a-custom-linkification-filter), regular
expression patterns that are automatically linkified when they appear
in messages and topics.

`GET {{ api_url }}/v1/realm/filters`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/filters:get|example}

{tab|curl}

```
curl {{ api_url }}/v1/realm/filters \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
```

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
