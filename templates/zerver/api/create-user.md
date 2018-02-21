# Create a user

Create a new user in a realm.

**Note**: The requesting user must be an administrator.

`POST {{ api_url }}/v1/users`

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
curl {{ api_url }}/v1/users \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "email=newbie@zulip.com" \
    -d "full_name=New User" \
    -d "short_name=newbie" \
    -d "password=temp"

```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|create-user|example(admin_config=True)}

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// You need a zuliprc-admin with administrator credentials
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
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|arguments.json|create-user.md}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|create-user|fixture(successful_response)}

A typical JSON response for when another user with the same
email address already exists in the realm:

{generate_code_example|create-user|fixture(email_already_used_error)}
