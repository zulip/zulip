# Get profile

Get the profile of the user/bot that requests this endpoint.

`GET {{ api_url }}/v1/users/me`

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
curl {{ api_url }}/v1/users/me \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|get-profile|example}

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
    // Get the profile of the user/bot that requests this endpoint,
    // which is `client` in this case:
    client.users.me.getProfile().then(console.log);
});
```
</div>

</div>

</div>

## Arguments

This endpoint takes no arguments.

## Response

#### Return values

* `pointer`: The integer ID of the message that the pointer is currently on.
* `max_message_id`: The integer ID of the last message by the user/bot with
  the given profile.

The rest of the return values are quite self-descriptive.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|get-profile|fixture}
