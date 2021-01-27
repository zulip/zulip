# Update subscription settings

{generate_api_description(/users/me/subscriptions/properties:post)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions/properties:post|example}

{tab|curl}

{generate_code_example(curl)|/users/me/subscriptions/properties:post|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions/properties:post}

The possible values for each `property` and `value` pairs are:

* `color` (string): the hex value of the user's display color for the stream.
* `is_muted` (boolean): whether the stream is
  [muted](/help/mute-a-stream).  Prior to Zulip 2.1, this feature was
  represented by the more confusingly named `in_home_view` (with the
  opposite value, `in_home_view=!is_muted`); for
  backwards-compatibility, modern Zulip still accepts that value.
* `pin_to_top` (boolean): whether to pin the stream at the top of the stream list.
* `desktop_notifications` (boolean): whether to show desktop notifications
    for all messages sent to the stream.
* `audible_notifications` (boolean): whether to play a sound
  notification for all messages sent to the stream.
* `push_notifications` (boolean): whether to trigger a mobile push
    notification for all messages sent to the stream.
* `email_notifications` (boolean): whether to trigger an email
    notification for all messages sent to the stream.

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/me/subscriptions/properties:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions/properties:post|fixture(200)}
