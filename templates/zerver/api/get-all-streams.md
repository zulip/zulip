# Get all streams

Get all streams that the user has access to.

`GET {{ api_url }}/v1/streams`

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
curl {{ api_url }}/v1/streams -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

You may pass in one or more of the parameters mentioned above
as URL query parameters, like so:

```
curl {{ api_url }}/v1/streams?include_public=false \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|get-all-streams|example}

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
    // Get all streams that the user has access to
    client.streams.retrieve().then(console.log);
});

```
</div>

</div>

</div>

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|arguments.json|get-all-streams.md}

## Response

#### Return values

* `stream_id`: The unique ID of a stream.
* `name`: The name of a stream.
* `description`: A short description of a stream.
* `invite-only`: Specifies whether a stream is invite-only or not.
  Only people who have been invited can access an invite-only stream.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|get-all-streams|fixture}

An example of a JSON response for when the user is not authorized
to use the `include_all_active` parameter:

{generate_code_example|user-not-authorized-error|fixture}
