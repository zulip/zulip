# Get all users

{generate_api_description(/users:get)}

You can also [fetch details on a single user](/api/get-user).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Get all users in the realm
    client.users.retrieve().then(console.log);

    // You may pass the `client_gravatar` query parameter as follows:
    client.users.retrieve({client_gravatar: true}).then(console.log);
});
```

{tab|curl}

{generate_code_example(curl, include=[""])|/users:get|example}

You may pass the `client_gravatar` query parameter as follows:

{generate_code_example(curl)|/users:get|example}

{end_tabs}

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/users:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users:get|fixture(200)}
