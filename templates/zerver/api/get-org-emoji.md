# Get all custom emoji

Get all the custom emoji in the user's organization.

`GET {{ api_url }}/v1/realm/emoji`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/realm/emoji:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    return client.emojis.retrieve();
}).then(console.log);
```

{tab|curl}

```
curl {{ api_url }}/v1/realm/emoji \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/realm/emoji:get}

## Response

#### Return values

* `emoji`: An object that contains `emoji` objects, each identified with their
    emoji ID as the key, and containing the following properties:
    * `id`: The ID for this emoji, same as the object's key.
    * `name`: The user-friendly name for this emoji. Users in the organization
        can use this emoji by writing this name between colons (`:name:`).
    * `source_url`: The path relative to the organization's URL where the
        emoji's image can be found.
    * `deactivated`: Whether the emoji has been deactivated or not.
    * `author`: An object describing the user who created the custom emoji,
        with the following fields:
        * `id`: The creator's user ID.
        * `email`: The creator's email address.
        * `full_name`: The creator's full name.


#### Example response

A typical successful JSON response may look like:

{generate_code_example|/realm/emoji:get|fixture(200)}
