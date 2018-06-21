# Fetch a development API key

Gather a token bound to a user account, to identify and authenticate them when
making operations with the API.

This token must be used as the password in the rest of the endpoints that
require Basic authentication.

**Note:** this endpoint is only for development environments! It will not work
if `settings.PRODUCTION` is set to `False`.

`POST {{ api_url }}/v1/dev_fetch_api_key`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/dev_fetch_api_key \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "username=iago@zulip.com"
```

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/dev_fetch_api_key:post}

## Response

#### Return values

* `api_key`: The API key that can be used to authenticate as the requested
    user.
* `email`: The email address of the user who owns the API key.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/dev_fetch_api_key:post|fixture(200)}
