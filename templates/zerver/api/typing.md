# Set "typing" status

Send an event indicating that the user has started or stopped typing
on their client.  See
[the typing notification docs](https://zulip.readthedocs.io/en/latest/subsystems/typing-indicators.html)
for details on Zulip's typing notifications protocol.

`POST {{ api_url }}/v1/typing`

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
curl -X POST {{ api_url }}/v1/typing \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "op=start" \
    -d 'to="iago@zulip.com","polonius@zulip.com"'
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/typing:post|example}

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Download zuliprc-dev from your dev server
const config = {
    zuliprc: 'zuliprc-dev',
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
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/typing:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/typing:post|fixture(200)}
