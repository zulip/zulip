# Get user presence

Get the presence status for a specific user.

This endpoint is especially useful for fetching statistics on a given user's
Zulip presence status, like how much time have they been connected.

`GET {{ api_url }}/v1/users/<email>/presence`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/users/<email>/presence \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/users/{email}/presence:get|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/{email}/presence:get}

## Response

#### Return values

* `presence`: An object containing the presence details for every client the
  user has logged into.
    * `<client_name>` or `aggregated`: the keys for these objects are the names
      of the different clients where this user is logged in, like `website` or
      `ZulipMobile`. There is also an `aggregated` key, which matches the
      contents of the object that has been updated most recently. In the
      majority of cases, you will want to look just at this field.
        * `status`: either `active` or `idle`.
        * `timestamp`: when was this update received.
        * `pushable`: whether the client accepts push notifications or not.
        * `client`: the name of the client this presence information refers to.
          Matches the object's key if this isn't the `aggregated` object.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/{email}/presence:get|fixture(200)}
