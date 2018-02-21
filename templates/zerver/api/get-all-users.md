# Get all users

Retrieve all users in a realm.

`GET {{ api_url }}/v1/users`

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
curl {{ api_url }}/v1/users -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

You may pass the `client_gravatar` query parameter as follows:

```
curl {{ api_url }}/v1/users?client_gravatar=true \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|get-all-users|example}

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

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|arguments.json|get-all-users.md}

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

{generate_code_example|get-all-users|fixture}
