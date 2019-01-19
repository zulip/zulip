# Get global settings

Fetch global settings for a Zulip server.

`GET {{ api_url }}/v1/server_settings`

**Note:** this endpoint does not require any authentication at all, and you can use it to check:

* If this is a Zulip server, and if so, what version of Zulip it's running.
* What a Zulip client (e.g. a mobile app or
  [zulip-terminal](https://github.com/zulip/zulip-terminal/)) needs to
  know in order to display a login prompt for the server (e.g. what
  authentication methods are available).

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/server_settings:get|example}

{tab|curl}

```
curl {{ api_url }}/v1/server_settings \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/server_settings:get}

## Response

#### Return values

* `authentication_methods`: object in which each key-value pair in the object
  indicates whether the authentication method is enabled on this server.
* `zulip_version`: the version of Zulip running in the server.
* `push_notifications_enabled`: whether mobile/push notifications are enabled.
* `email_auth_enabled`: setting for allowing users authenticate with an
  email-password combination.
* `require_email_format_usernames`: whether usernames should have an
  email address format. This is important for clients to know whether
  the validate email address format in a login prompt; this value will
  be false if the server has
  [LDAP authentication][ldap-auth]
  enabled with a username and password combination.
* `realm_uri`: the organization's canonical URI.
* `realm_name`: the organization's name (for display purposes).
* `realm_icon`: the URI of the organization's logo as a square image,
  used for identifying the organization in small locations in the
  mobile and desktop apps.
* `realm_logo`: the URI of the organization's logo as a horizontal
  format image (displayed in the top-left corner of the logged-in
  webapp).
* `realm_night_logo`: the URI of the organization's logo in the night mode as a
  horizontal format image (dispalyed in the top-left corner of the logged-in
  webapp).
* `realm_description`: HTML description of the organization, as configured by
  the [organization profile](/help/create-your-organization-profile).

[ldap-auth]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory

Please note that not all of these attributes are guaranteed to appear in a
response, for two reasons:

* This endpoint has evolved over time, so responses from older Zulip servers
  might be missing some keys (in which case a client should assume the
  appropriate default).
* If a `/server_settings` request is made to the root domain of a
  multi-subdomain server, like the root domain of zulipchat.com, the settings
  that are realm-specific are not known and thus not provided.

#### Example response

A typical successful JSON response for a single-organization server may look like:

{generate_code_example|/server_settings:get|fixture(200)}
