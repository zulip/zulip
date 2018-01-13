# Get all users

Retrieve all users in a realm.

`GET {{ api_url }}/v1/users`

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|arguments.json|get-all-users.md}

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
curl {{ api_url }}/v1/users -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

You may pass the `client_gravatar` query parameter as follows:

```
curl {{ api_url }}/v1/users?client_gravatar=true \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

```python
#!/usr/bin/env python

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Get all users in the realm
print(client.get_members())

# You may pass the `client_gravatar` query parameter as follows:
print(client.call_endpoint(
    url='users?client_gravatar=true',
    method='GET',
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
    // Get all users in the realm
    client.users.retrieve().then(console.log);

    // You may pass the `client_gravatar` query parameter as follows:
    client.users.retrieve({client_gravatar: true}).then(console.log);
});
```
</div>

</div>

</div>

## Response

#### Return values

* `members`: A list of dictionaries where each dictionary contains information
  about a particular user or bot.
    * `email`: The email address of the user or bot..
    * `is_bot`: A boolean specifying whether the user is a bot or not.
    * `avatar_url`: URL to the user's gravatar. `None` if the `client_gravatar`
      query paramater was set to `True`.
    * `full_name`: Full name of the user or bot.
    * `is_admin`: A boolean specifying whether the user is an admin or not.
    * `bot_type`: `None` if the user isn't a bot. `1` for a `Generic` bot.
      `2` for an `Incoming webhook` bot. `3` for an `Outgoing webhook` bot.
      `4` for an `Embedded` bot.
    * `user_id`: The ID of the user.
    * `bot_owner`: If the user is a bot (i.e. `is_bot` is `True`), `bot_owner`
      is the email address of the user who created the bot.
    * `is_active`: A boolean specifying whether the user is active or not.

#### Example response

A typical successful JSON response may look like:

```
{
    'msg':'',
    'members':[
        {
            'email':'ZOE@zulip.com',
            'is_bot':False,
            'avatar_url':'https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d=identicon&version=1',
            'full_name':'Zoe',
            'is_active':True,
            'is_admin':False,
            'bot_type':None,
            'user_id':23
        },
        {
            'email':'AARON@zulip.com',
            'is_bot':False,
            'avatar_url':'https://secure.gravatar.com/avatar/818c212b9f8830dfef491b3f7da99a14?d=identicon&version=1',
            'full_name':'aaron',
            'is_active':True,
            'is_admin':False,
            'bot_type':None,
            'user_id':22
        },
        {
            'bot_owner':'iago@zulip.com',
            'email':'sample-bot@localhost',
            'is_bot':True,
            'avatar_url':'https://secure.gravatar.com/avatar/0ea4ba8ec99b1fe07f62785a7c584cd3?d=identicon&version=1',
            'full_name':'sample',
            'is_active':True,
            'is_admin':False,
            'bot_type':1,
            'user_id':45
        },
        {
            'email':'iago@zulip.com',
            'is_bot':False,
            'avatar_url':'https://secure.gravatar.com/avatar/af4f06322c177ef4e1e9b2c424986b54?d=identicon&version=1',
            'full_name':'Iago',
            'is_active':True,
            'is_admin':True,
            'bot_type':None,
            'user_id':26
        }
    ],
    'result':'success'
}
```

{!invalid-api-key-json-response.md!}
