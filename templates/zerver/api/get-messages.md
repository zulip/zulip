# Get messages

Fetch messages that match a specific narrow.

`GET {{ api_url }}/v1/messages`

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
curl {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "anchor=42" \
    -d "use_first_unread_anchor=false" \
    -d "num_before=3" \
    -d "num_after=14" \
    -d "narrow=[{\"operator\":\"stream\", \"operand\":\"party\"}]" \

```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/messages:get|example}

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
    const readParams = {
        stream,
        type: 'stream',
        anchor: res.id,
        num_before: 1,
        num_after: 1,
    };

    // Fetch messages anchored around id (1 before, 1 after)
    return client.messages.retrieve(readParams);
}).then(console.log);
```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages:get}

## Response

#### Return values

* `anchor`: the same `anchor` specified in the request.
* `found_newest`: whether the `messages` list includes the latest message in
    the narrow.
* `found_oldest`: whether the `messages` list includes the oldest message in
    the narrow.
* `found_anchor`: whether it was possible to fetch the requested anchor, or
    the closest in the narrow has been used.
* `messages`: an array of `message` objects, each containing the following
    fields:
    * `avatar_url`
    * `client`
    * `content`
    * `content_type`
    * `display_recipient`
    * `flags`
    * `id`
    * `is_me_message`
    * `reactions`
    * `recipient_id`
    * `sender_email`
    * `sender_full_name`
    * `sender_id`
    * `sender_realm_str`
    * `sender_short_name`
    * `stream_id`: this is only shown in stream messages.
    * `subject`: this will be empty on PMs.
    * `subject_links`
    * `submessages`
    * `timestamp`
    * `type`

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages:get|fixture(200)}
