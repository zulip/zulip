# Create a user

{!api-admin-only.md!}

Create a new user account via the API.

`POST {{ api_url }}/v1/users`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users:post|example(admin_config=True)}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// The user for this zuliprc file must be an organization administrator.
const config = {
    zuliprc: 'zuliprc-admin',
};

zulip(config).then((client) => {
    // Create a user
    const params = {
        email: 'newbie@zulip.com',
        password: 'temp',
        full_name: 'New User',
        short_name: 'newbie'
    };
    client.users.create(params).then(console.log);
});
```

{tab|curl}

{generate_code_example(curl)|/users:post|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users:post|fixture(200)}

A typical JSON response for when another user with the same
email address already exists in the realm:

{generate_code_example|/users:post|fixture(400)}
