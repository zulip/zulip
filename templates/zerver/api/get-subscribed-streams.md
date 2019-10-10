# Get subscribed streams

Get all streams that the user is subscribed to.

`GET {{ api_url }}/v1/users/me/subscriptions`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Get all streams that the user is subscribed to
    client.streams.subscriptions.retrieve().then(console.log);
});

```

{tab|curl}

{generate_code_example(curl, include=[""])|/users/me/subscriptions:get|example}

You may pass the `include_subscribers` query parameter as follows:

{generate_code_example(curl)|/users/me/subscriptions:get|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:get}

## Response

#### Return values

* `subscriptions`: A list of dictionaries where each dictionary contains
  information about one of the subscribed streams.
    * `stream_id`: The unique ID of a stream.
    * `name`: The name of a stream.
    * `description`: A short description of a stream.
    * `invite-only`: Specifies whether a stream is private or not.
      Only people who have been invited can access a private stream.
    * `subscribers`: A list of email addresses of users who are also subscribed
      to a given stream. Included only if `include_subscribers` is `true`.
    * `desktop_notifications`: A boolean specifiying whether desktop notifications
      are enabled for the given stream.
    * `push_notifications`: A boolean specifiying whether push notifications
      are enabled for the given stream.
    * `audible_notifications`: A boolean specifiying whether audible notifications
      are enabled for the given stream.
    * `pin_to_top`: A boolean specifying whether the given stream has been pinned
      to the top.
    * `email_address`: Email address of the given stream.
    * `in_home_view`: Whether the given stream is muted or not. Muted streams do
      not count towards your total unread count and thus, do not show up in
      `All messages` view (previously known as `Home` view).
    * `color`: Stream color.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions:get|fixture(200)}
