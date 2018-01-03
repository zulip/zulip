# Get all streams

Get all streams that the user has access to.

`GET {{ api_url }}/v1/streams`

## Arguments

**Note**: The following arguments are all URL query parameters.

{generate_api_arguments_table|arguments.json|get-all-streams.md}

## Usage examples
<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
<li data-language="python">Python</li>
<li data-language="javascript">JavaScript</li>
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

```
#!/usr/bin/env python

import zulip
import sys

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

# Get all streams that the user has access to
print(client.get_streams())

# You may pass in one or more of the query parameters mentioned above
# as keyword arguments, like so:
print(client.get_streams(include_public=False))
```

</div>

<div data-language="javascript" markdown="1">
More examples and documentation can be found [here](https://github.com/zulip/zulip-js).
```js
const zulip = require('zulip-js');

const config = {
  username: 'othello-bot@example.com',
  apiKey: 'a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5',
  realm: '{{ api_url }}'
};

const client = zulip(config);

// Get all streams that the user has access to
client.streams.retrieve().then(res => {
    console.log(res);
});

```
</div>

</div>

</div>

## Response

#### Return values

* `stream_id`: The unique ID of a stream.
* `name`: The name of a stream.
* `description`: A short description of a stream.
* `invite-only`: Specifies whether a stream is invite-only or not.
  Only people who have been invited can access an invite-only stream.

#### Example response

A typical successful JSON response may look like:

```
{
    'result':'success',
    'streams':[
        {
            'stream_id':15,
            'name':'Denmark',
            'invite_only':False,
            'description':'A Scandinavian country'
        },
        {
            'stream_id':16,
            'name':'Rome',
            'invite_only':False,
            'description':'Yet another Italian city'
        },
        {
            'stream_id':17,
            'name':'Scotland',
            'invite_only':False,
            'description':'Located in the United Kingdom'
        },
        {
            'stream_id':18,
            'name':'Venice',
            'invite_only':False,
            'description':'A northeastern Italian city'
        },
        {
            'stream_id':19,
            'name':'Verona',
            'invite_only':False,
            'description':'A city in Italy'
        }
    ],
    'msg':''
}
```

An example of a JSON response for when the user is not authorized
to use the `include_all_active` parameter:

```
{
    'code':'BAD_REQUEST',
    'result':'error',
    'msg':'User not authorized for this query'
}
```

{!invalid-api-key-json-response.md!}
