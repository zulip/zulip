# Render message

Render a message to HTML.

`POST {{ api_url }}/v1/messages/render`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/render:post|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Render a message
    const params = {
        content: '**foo**',
    };

    client.messages.render(params).then(console.log);
});
```

{tab|curl}

```
curl {{ api_url }}/v1/messages/render \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d $"content=**foo**"

```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/render:post}

## Response

#### Return values

* `rendered`: The rendered HTML.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/render:post|fixture(200)}
