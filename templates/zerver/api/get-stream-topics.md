# Get topics in a stream

Get all the topics in a specific stream

`GET {{ api_url }}/v1/users/me/<stream_id>/topics`

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
curl {{ api_url }}/v1/users/me/<stream_id>/topics \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/users/me/{stream_id}/topics:get|example}

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Download zuliprc-dev from your dev server, assuming it's in the local dir
const config = {
    zuliprc: 'zuliprc-dev',
};

zulip(config).then((client) => {
    // Get all the topics in stream with ID 1
    return client.streams.topics.retrieve({ stream_id: 1 });
}).then(console.log);

```
</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/{stream_id}/topics:get}

## Response

#### Return values

* `topics`: An array of `topic` objects, which contain:
    * `name`: The name of the topic.
    * `max_id`: The message ID of the last message sent to this topic.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/{stream_id}/topics:get|fixture(200)}

An example JSON response for when the user is attempting to fetch the topics
of a non-existing stream (or also a private stream they don't have access to):

{generate_code_example|/users/me/{stream_id}/topics:get|fixture(400)}
