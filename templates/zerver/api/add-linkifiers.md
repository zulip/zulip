# Create linkifiers

Configure [linkifiers](/help/add-a-custom-linkification-filter),
regular expression patterns that are automatically linkified when they
appear in messages and topics.

`POST {{ api_url }}/v1/realm/filters`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/filters:post|example}

{tab|curl}

```
curl -X POST {{ api_url }}/v1/realm/filters \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "pattern=#(?P<id>[0-9]+)" \
    -d "url_format_string=https://github.com/zulip/zulip/issues/%(id)s"
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/realm/filters:post}

## Response

#### Return values

* `id`: The numeric ID assigned to this filter.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/filters:post|fixture(200)}
