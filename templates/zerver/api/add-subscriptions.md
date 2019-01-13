# Add subscriptions

Subscribe one or more users to one or more streams.

`POST {{ api_url }}/v1/users/me/subscriptions`

If any of the specified streams do not exist, they are automatically
created, and configured using the `invite_only` setting specified in
the arguments (see below).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|add-subscriptions|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
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

{tab|curl}

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

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:post}

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

{generate_code_example|/users/me/subscriptions:post|fixture(200_without_principals)}

A typical successful JSON response when the user is already subscribed to
the streams specified:

{generate_code_example|/users/me/subscriptions:post|fixture(200_already_subscribed)}

A typical response for when the requesting user does not have access to
a private stream and `authorization_errors_fatal` is `True`:

{generate_code_example|/users/me/subscriptions:post|fixture(400_unauthorized_errors_fatal_true)}


A typical response for when the requesting user does not have access to
a private stream and `authorization_errors_fatal` is `False`:

{generate_code_example|/users/me/subscriptions:post|fixture(400_unauthorized_errors_fatal_false)}
