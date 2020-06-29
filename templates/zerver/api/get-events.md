# Get events from an event queue

{generate_api_description(/events:get)}

## Usage examples

{start_tabs}
{tab|python}

```
#!/usr/bin/env python

import sys
import zulip

# Pass the path to your zuliprc file here.
client = zulip.Client(config_file="~/zuliprc")

# If you already have a queue registered and thus, have a queue_id
# on hand, you may use client.get_events() and pass in the above
# parameters, like so:
print(client.get_events(
    queue_id="1515010080:4",
    last_event_id=-1
))
```

`call_on_each_message` and `call_on_each_event` will automatically register
a queue for you.

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/events:get|example}

{tab|curl}

{generate_code_example(curl, include=["queue_id", "last_event_id"])|/events:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/events:get}

**Note**: The parameters documented above are optional in the sense that
even if you haven't registered a queue by explicitly requesting the
`{{ api_url}}/v1/register` endpoint, you could pass the parameters for
[the `{{ api_url}}/v1/register` endpoint](/api/register-queue) to this
endpoint and a queue would be registered in the absence of a `queue_id`.

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/events:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/events:get|fixture(200)}

#### BAD_EVENT_QUEUE_ID errors

If the target event queue has been garbage collected, you'll get the
following error response:

{generate_code_example|/events:get|fixture(400)}

A compliant client will handle this error by re-initializing itself
(e.g. a Zulip webapp browser window will reload in this case).

See [the /register endpoint docs](/api/register-queue) for details on how to
handle these correctly.
