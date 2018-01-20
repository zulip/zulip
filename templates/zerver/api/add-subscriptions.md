# Add subscriptions

Subscribe one or more users to one or more streams.

`POST {{ api_url }}/v1/users/me/subcriptions`

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
curl {{ api_url }}/v1/users/me/subscriptions \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'subscriptions=[{"name": "Verona"}]'
```

To subscribe another user to a stream, you may pass in
the `principals` argument, like so:

```
curl {{ api_url }}/v1/users/me/subscriptions \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'subscriptions=[{"name": "Verona"}]' \
    -d 'principals=["ZOE@zulip.com"]'
```

</div>

<div data-language="python" markdown="1">

```python
#!/usr/bin/env python

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Subscribe to the streams "Verona" and "Denmark"
print(client.add_subscriptions(
    streams=[
        {'name': 'Verona'},
        {'name': 'Denmark'}
    ]
))

# To subscribe another user to a stream, you may pass in
# the `principals` argument, like so:
print(client.add_subscriptions(
    streams=[
        {'name': 'Verona'},
        {'name': 'Denmark'}
    ],
    principals=['ZOE@zulip.org']
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
    // Subscribe to the streams "Verona" and "Denmark"
    const meParams = {
        subscriptions: JSON.stringify([
            {'name': 'Verona'},
            {'name': 'Denmark'}
        ]),
    };
    client.users.me.subscriptions.add(meParams).then(console.log);

    // To subscribe another user to a stream, you may pass in
    // the `principals` argument, like so:
    const anotherUserParams = {
        subscriptions: JSON.stringify([
            {'name': 'Verona'},
            {'name': 'Denmark'}
        ]),
        principals: JSON.stringify(['ZOE@zulip.org']),
    };
    client.users.me.subscriptions.add(anotherUserParams).then(console.log);
});
```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|add-subscriptions.md}

## Response

#### Return values

* `subscribed`: A dictionary where the key is the email address of
  the user/bot and the value is a list of the names of the streams
  that were subscribed to as a result of the query.

* `already_subscribed`: A dictionary where the key is the email address of
  the user/bot and the value is a list of the names of the streams
  that the user/bot is already subscribed to.

* `unauthorized`: A list of names of streams that the requesting user/bot
  was not authorized to subscribe to.

#### Example response

A typical successful JSON response may look like:

```
{
    'msg':'',
    'result':'success',
    'already_subscribed':{

    },
    'subscribed':{
        'sample-bot@localhost':[
            'Denmark',
            'Verona'
        ]
    }
}
```

A typical successful JSON response when the user is already subscribed to
the streams specified:

```
{
    'subscribed':{

    },
    'msg':'',
    'result':'success',
    'already_subscribed':{
        'sample-bot@localhost':[
            'Nonexistent',
            'Verona'
        ]
    }
}
```

A typical response for when the requesting user does not have access to
a private stream and `authorization_errors_fatal` is `True`:

```
{
    "msg":"Unable to access stream (yaar).",
    "result":"error"
}
```

A typical response for when the requesting user does not have access to
a private stream and `authorization_errors_fatal` is `False`:

```
{
    "unauthorized":[
        "yaar"
    ],
    "subscribed":{

    },
    "msg":"",
    "result":"success",
    "already_subscribed":{

    }
}
```

{!invalid-api-key-json-response.md!}
