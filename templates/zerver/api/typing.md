# Set "typing" status

Send an event indicating that the user has started or stopped typing
on their client.  See
[the typing notification docs](https://zulip.readthedocs.io/en/latest/subsystems/typing-indicators.html)
for details on Zulip's typing notifications protocol.

`POST {{ api_url }}/v1/typing`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/typing:post|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

const typingParams = {
    op: 'start',
    to: ['iago@zulip.com', 'polonius@zulip.com'],
};

zulip(config).then((client) => {
    // The user has started to type in the group PM with Iago and Polonius
    return client.typing.send(typingParams);
}).then(console.log);
```

{tab|curl}

```
curl -X POST {{ api_url }}/v1/typing \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "op=start" \
    -d 'to="iago@zulip.com","polonius@zulip.com"'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/typing:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/typing:post|fixture(200)}
