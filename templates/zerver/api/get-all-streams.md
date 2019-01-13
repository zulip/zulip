# Get all streams

Get all streams that the user has access to.

`GET {{ api_url }}/v1/streams`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/streams:get|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

// Pass the path to your zuliprc file here.
const config = {
    zuliprc: 'zuliprc',
};

zulip(config).then((client) => {
    // Get all streams that the user has access to
    client.streams.retrieve().then(console.log);
});

```

{tab|curl}

```
curl {{ api_url }}/v1/streams -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

You may pass in one or more of the parameters mentioned above
as URL query parameters, like so:

```
curl {{ api_url }}/v1/streams?include_public=false \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|zulip.yaml|/streams:get}

## Response

#### Return values

* `stream_id`: The unique ID of a stream.
* `name`: The name of a stream.
* `description`: A short description of a stream.
* `invite-only`: Specifies whether a stream is private or not.
  Only people who have been invited can access a private stream.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/streams:get|fixture(200)}

An example JSON response for when the user is not authorized to use the
`include_all_active` parameter (i.e. because they are not an organization
administrator):

{generate_code_example|/streams:get|fixture(400)}
