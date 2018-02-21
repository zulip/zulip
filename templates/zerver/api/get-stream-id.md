# Get stream ID

Get the unique ID of a given stream.

`GET {{ api_url }}/v1/get_stream_id`

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
curl {{ api_url }}/v1/get_stream_id?stream=Denmark \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```
</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|get-stream-id|example}

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
    // Get the ID of a given stream
    client.streams.getStreamId('Denmark').then(console.log);
});
```
</div>

</div>

</div>

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|arguments.json|get-stream-id.md}

## Response

#### Return values

* `stream_id`: The ID of the given stream.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|get-stream-id|fixture}

An example of a JSON response for when the supplied stream does not
exist:

{generate_code_example|invalid-stream-error|fixture}
