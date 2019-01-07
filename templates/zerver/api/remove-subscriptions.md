# Remove subscriptions

Unsubscribe yourself or other users from one or more streams.

`DELETE {{ api_url }}/v1/users/me/subcriptions`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:delete|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
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

{tab|curl}

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

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:delete}

#### Return values

* `removed`: A list of the names of streams which were unsubscribed from as
  a result of the query.

* `not_subscribed`: A list of the names of streams that the user is already
  unsubscribed from, and hence doesn't need to be unsubscribed.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions:delete|fixture(200)}

A typical failed JSON response for when the target stream does not exist:

{generate_code_example|/users/me/subscriptions:delete|fixture(400)}
