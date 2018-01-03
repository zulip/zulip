# Get stream ID

Get the unique ID of a given stream.

`GET {{ api_url }}/v1/get_stream_id`

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|arguments.json|get-stream-id.md}

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/get_stream_id?stream=Denmark \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```
</div>

<div data-language="python" markdown="1">

```python
#!/usr/bin/env python

import zulip
import sys

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Get the ID of a given stream
print(client.get_stream_id("Denmark"))
```
</div>

</div>

</div>

## Response

#### Return values

* `stream_id`: The ID of the given stream.

#### Example response

A typical successful JSON response may look like:

```
{
    'stream_id':15,
    'result':'success',
    'msg':''
}
```

An example of a JSON response for when the supplied stream does not
exist:

```
{
    'code':'BAD_REQUEST',
    'msg':"Invalid stream name 'nonexistent'",
    'result':'error'
}
```

An example of a JSON response for when the `stream` query parameter is
not provided:

```
{
    "msg":"Missing 'stream' argument",
    "result":"error",
    "var_name":"stream",
    "code":"REQUEST_VARIABLE_MISSING"
}
```

{!invalid-api-key-json-response.md!}
