# Create organization filters

Establish patterns in the messages that should be automatically linkified.

`POST {{ api_url }}/v1/realm/filters`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl -X POST {{ api_url }}/v1/realm/filters \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "pattern=#(?P<id>[0-9]+)" \
    -d "url_format_string=https://github.com/zulip/zulip/issues/%(id)s"
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/realm/filters:post|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/realm/filters:post}

## Response

#### Return values

* `id`: The numeric ID assigned to this filter.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/filters:post|fixture(200)}
