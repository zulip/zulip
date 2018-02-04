# Remove subscriptions

Unsubscribe yourself or other users from one or more streams.

`DELETE {{ api_url }}/v1/users/me/subcriptions`

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
curl -X "DELETE" {{ api_url }}/v1/users/me/subscriptions \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'subscriptions=["Denmark"]'
```

You may specify the `principals` argument like so:

```
curl -X "DELETE" {{ api_url }}/v1/users/me/subscriptions \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'subscriptions=["Denmark"]' \
    -d 'principals=["ZOE@zulip.com"]'
```

**Note**: Unsubscribing another user from a stream requires
administrative privileges.
</div>

<div data-language="python" markdown="1">

```python
#!/usr/bin/env python

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Unsubscribe from the stream "Denmark"
print(client.remove_subscriptions(
    ['Denmark']
))

# Unsubscribe Zoe from the stream "Denmark"
print(client.remove_subscriptions(
    ['Denmark'],
    principals=['ZOE@zulip.com']
))
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
    // Unsubscribe from the stream "Denmark"
    const meParams = {
        subscriptions: JSON.stringify(['Denmark']),
    };
    client.users.me.subscriptions.remove(meParams).then(console.log);

    // Unsubscribe Zoe from the stream "Denmark"
    const zoeParams = {
        subscriptions: JSON.stringify(['Denmark']),
        principals: JSON.stringify(['ZOE@zulip.org']),
    };
    client.users.me.subscriptions.remove(zoeParams).then(console.log);
});
```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|remove-subscriptions.md}

#### Return values

* `removed`: A list of the names of streams which were unsubscribed from as
  a result of the query.

* `not_subscribed`: A list of the names of streams that the user is already
  unsubscribed from, and hence doesn't need to be unsubscribed.

#### Example response

A typical successful JSON response may look like:

```
{
    "result":"success",
    "not_subscribed":[

    ],
    "msg":"",
    "removed":[
        "Denmark"
    ]
}
```

A typical JSON response for when you try to unsubscribe from a stream
that doesn't exist:

```
{
    "msg":"Stream(s) (Denmarkk) do not exist",
    "code":"BAD_REQUEST",
    "result":"error"
}
```

{!invalid-api-key-json-response.md!}
