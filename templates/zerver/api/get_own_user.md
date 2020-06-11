# Get profile

{generate_api_description(/users/me:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Get the profile of the user/bot that requests this endpoint,
    // which is `client` in this case:
    client.users.me.getProfile().then(console.log);
});
```

{tab|curl}

{generate_code_example(curl)|/users/me:get|example}

{end_tabs}

## Arguments

This endpoint takes no arguments.

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/me:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me:get|fixture(200)}
