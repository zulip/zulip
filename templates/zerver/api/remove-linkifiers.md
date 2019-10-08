# Remove linkifiers

Remove [linkifiers](/help/add-a-custom-linkification-filter), regular
expression patterns that are automatically linkified when they appear
in messages and topics.

`DELETE {{ api_url }}/v1/realm/filters/<filter_id>`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/filters/<filter_id>:delete|example}

{tab|curl}

```
curl -X DELETE {{ api_url }}/v1/realm/filters/<filter_id> \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/realm/filters/<filter_id>:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/filters/<filter_id>:delete|fixture(200)}
