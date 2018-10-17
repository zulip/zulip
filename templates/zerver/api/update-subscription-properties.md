# Update subscription properties

This endpoint is used to update the user's personal settings for the
streams they are subscribed to, including muting, color, pinning, and
per-stream notification settings.

`POST {{ api_url }}/v1/users/me/subscriptions/properties`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions/properties:post|example}

{tab|curl}

```
curl -X POST {{ api_url }}/v1/users/me/subscriptions/properties \
     -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
     -d 'subscription_data=[{"stream_id": 1, \
                             "property": "pin_to_top", \
                             "value": true}, \
                            {"stream_id": 3, \
                             "property": "color", \
                             "value": 'f00'}]'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions/properties:post}

The possible values for each `property` and `value` pairs are:

* `color` (string): the hex value of the user's display color for the stream.
* `in_home_view` (boolean): whether the stream should be visible in the home
    view (`true`) or muted and thus hidden from the home view (`false`).
* `pin_to_top` (boolean): whether to pin the stream at the top of the stream list.
* `desktop_notifications` (boolean): whether to show desktop notifications
    for all messages sent to the stream.
* `audible_notifications` (boolean): whether to play a sound
  notification for all messages sent to the stream.
* `push_notifications` (boolean): whether to trigger a mobile push
    notification for all messages sent to the stream.

## Response

#### Return values

* `subscription_data`: The same `subscription_data` object sent by the client
    for the request, confirming the changes made.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions/properties:post|fixture(200)}
