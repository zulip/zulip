# Render message

Render a message to HTML.

`POST {{ api_url }}/v1/messages/render`

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
curl {{ api_url }}/v1/messages/render \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "content=**foo**"

```
</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/messages/render:post|example}

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Download zuliprc-dev from your dev server
const config = {
    zuliprc: 'zuliprc-dev',
};

zulip(config).then((client) => {
    // Render a message
    const params = {
        content: '**foo**',
    };

    client.messages.render(params).then(console.log);
});
```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/render:post}

## Response

#### Return values

* `rendered`: The rendered HTML.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/render:post|fixture(200)}
