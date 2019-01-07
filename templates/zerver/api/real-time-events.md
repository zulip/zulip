# Real-time events API

Zulip's real-time events API lets you write software that reacts
immediately to events happening in Zulip.  This API is what powers the
real-time updates in the Zulip web and mobile apps.  As a result, the
events available via this API cover all changes to data displayed in
the Zulip product, from new messages to stream descriptions to
emoji reactions to changes in user or organization-level settings.

## Using the events API

The simplest way to use Zulip's real-time events API is by using
`call_on_each_event` from our Python bindings.  You just need to write
a Python function (in the examples below, the `lambda`s) and pass it
into `call_on_each_event`; your function will be called whenever a new
event matching the specific `event_type` and/or `narrow` arguments
occurs in Zulip.

`call_on_each_event` takes care of all the potentially tricky details
of long-polling, error handling, exponential backoff in retries, etc.
It's cousin, `call_on_each_message`, provides an even simpler
interface for processing Zulip messages.

More complex applications (like a Zulip terminal client) may need to
instead use the raw [register](/api/register-queue) and
[events](/api/get-events-from-queue) endpoints.

## Usage examples

{start_tabs}
{tab|python}

```
#!/usr/bin/env python

import sys
import zulip

# Pass the path to your zuliprc file here.
client = zulip.Client(config_file="~/zuliprc")

# Print every message the current user would receive
# This is a blocking call that will run forever
client.call_on_each_message(lambda msg: sys.stdout.write(str(msg) + "\n"))

# Print every event relevant to the user
# This is a blocking call that will run forever
client.call_on_each_event(lambda event: sys.stdout.write(str(event) + "\n"))
```

{end_tabs}

## Arguments

You may also pass in the following keyword arguments to `call_on_each_event`:

{generate_api_arguments_table|arguments.json|call_on_each_event}
