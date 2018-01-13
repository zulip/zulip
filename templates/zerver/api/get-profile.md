# Get profile

Get the profile of the user/bot that requests this endpoint.

`GET {{ api_url }}/v1/users/me`

## Arguments

This endpoint takes no arguments.

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
<li data-language="javascript">JavaScript</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/users/me \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

```python
#!/usr/bin/env python

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Get the profile of the user/bot that requests this endpoint,
# which is `client` in this case:
print(client.get_profile())
```

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

## Response

#### Return values

* `pointer`: The integer ID of the message that the pointer is currently on.
* `max_message_id`: The integer ID of the last message by the user/bot with
  the given profile.

The rest of the return values are quite self-descriptive.

#### Example response

A typical successful JSON response may look like:

```
{
    'short_name':'sample-bot',
    'result':'success',
    'msg':'',
    'is_bot':True,
    'email':'sample-bot@localhost',
    'pointer':-1,
    'max_message_id':131,
    'full_name':'Sample',
    'user_id':45,
    'client_id':'77431db17e4f32068756902d7c09c8bb',
    'is_admin':False
}
```

{!invalid-api-key-json-response.md!}
