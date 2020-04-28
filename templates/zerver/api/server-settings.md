# Get global settings

{generate_api_description(/server_settings:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/server_settings:get|example}

{tab|curl}

{generate_code_example(curl)|/server_settings:get|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/server_settings:get}

## Response

#### Return values

* `authentication_methods`: object in which each key-value pair in the object
  indicates whether the authentication method is enabled on this server.
* `zulip_version`: the version of Zulip running in the server.
* `zulip_feature_level`: an integer indicatating what features are
    available on the server. The feature level increases monotonically;
    a value of N means the server supports all API features introduced
    before feature level N.  This is designed to provide a simple way
    for mobile apps to decide whether the server supports a given
    feature or API change.

    **Changes**.  New in Zulip 2.2.  We recommend using an implied value
    of 0 for Zulip servers that do not send this field.

* `push_notifications_enabled`: whether mobile/push notifications are enabled.
* `is_incompatible`: whether the Zulip client that has sent a request to
  this endpoint is deemed incompatible with the server.
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
* `realm_description`: HTML description of the organization, as configured by
  the [organization profile](/help/create-your-organization-profile).
* `external_authentication_methods`: list of dictionaries describing
  the available external authentication methods (such as
  google/github/SAML) enabled for this organization. Each dictionary
  specifies the name and icon that should be displayed on the login
  buttons (`display_name` and `display_icon`, where `display_icon` can
  be `null`, if no icon is to be displayed), the URLs that
  should be accessed to initiate login/signup using the method
  (`login_url` and `signup_url`) and `name`, which is a unique,
  stable, machine-readable name for the authentication method.  The
  list is sorted in the order in which these authentication methods
  should be displayed.

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
