# Get subscribed streams

Get all streams that the user is subscribed to.

`GET {{ api_url }}/v1/users/me/subscriptions`

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="javascript">JavaScript</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/users/me/subscriptions \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|get-subscribed-streams|example}

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

```js
const zulip = require('zulip-js');

// Download zuliprc-dev from your dev server
const config = {
    zuliprc: 'zuliprc-dev',
};

zulip(config).then((client) => {
    // Get all streams that the user is subscribed to
    client.streams.subscriptions.retrieve().then(console.log);
});

```
</div>

</div>

</div>

## Arguments

This request takes no arguments.

## Response

#### Return values

* `subscriptions`: A list of dictionaries where each dictionary contains
  information about one of the subscribed streams.
    * `stream_id`: The unique ID of a stream.
    * `name`: The name of a stream.
    * `description`: A short description of a stream.
    * `invite-only`: Specifies whether a stream is invite-only or not.
      Only people who have been invited can access an invite-only stream.
    * `subscribers`: A list of email addresses of users who are also subscribed
      to a given stream.
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

{generate_code_example|get-subscribed-streams|fixture}
