# Delete a queue

Delete a previously registered queue.

`DELETE {{ api_url }}/v1/events`

## Arguments

{generate_api_arguments_table|arguments.json|delete-queue.md}

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl -X "DELETE" {{ api_url }}/v1/events \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
    -d 'queue_id=1515096410:1'
```

</div>

<div data-language="python" markdown="1">

```python
#!/usr/bin/env python

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Delete a queue
print(client.deregister(queue_id="1515096410:1"))
```

</div>

</div>

</div>

## Response

#### Example response

A typical successful JSON response may look like:

```
{
    'msg':'',
    'result':'success'
}
```

A typical JSON response for when the `queue_id` is non-existent or the
associated queue has already been deleted:

```
{
    'code':'BAD_EVENT_QUEUE_ID',
    'queue_id':'1515096410:2',
    'result':'error',
    'msg':'Bad event queue id: 1515096410:2'
}
```

{!invalid-api-key-json-response.md!}
