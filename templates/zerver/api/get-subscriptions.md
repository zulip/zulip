# Get subscribed streams

{generate_api_description(/users/me/subscriptions:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Get all streams that the user is subscribed to
    client.streams.subscriptions.retrieve().then(console.log);
});

```

{tab|curl}

{generate_code_example(curl, include=[""])|/users/me/subscriptions:get|example}

You may pass the `include_subscribers` query parameter as follows:

{generate_code_example(curl)|/users/me/subscriptions:get|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/users/me/subscriptions:get}

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions:get|fixture(200)}
