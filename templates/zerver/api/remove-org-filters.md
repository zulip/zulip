# Remove organization filters

Remove an organization filter.

`DELETE {{ api_url }}/v1/realm/filters/<filter_id>`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl -X DELETE {{ api_url }}/v1/realm/filters/<filter_id> \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/realm/filters/<filter_id>:delete|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/realm/filters/<filter_id>:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/filters/<filter_id>:delete|fixture(200)}
