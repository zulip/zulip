# Render message

{generate_api_description(/messages/render:post)}

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

{generate_code_example(curl)|/messages/render:post|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/render:post}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/messages/render:post}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/render:post|fixture(200)}
