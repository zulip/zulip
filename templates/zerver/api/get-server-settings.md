# Get server settings

{generate_api_description(/server_settings:get)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/server_settings:get|example}

{tab|curl}

{generate_code_example(curl)|/server_settings:get|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/server_settings:get}

## Response

#### Return values

{generate_return_values_table|zulip.yaml|/server_settings:get}

[ldap-auth]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#ldap-including-active-directory

Please note that not all of these attributes are guaranteed to appear in a
response, for two reasons:

* This endpoint has evolved over time, so responses from older Zulip servers
  might be missing some keys (in which case a client should assume the
  appropriate default).
* If a `/server_settings` request is made to the root domain of a
  multi-subdomain server, like the root domain of zulip.com, the settings
  that are realm-specific are not known and thus not provided.

#### Example response

A typical successful JSON response for a single-organization server may look like:

{generate_code_example|/server_settings:get|fixture(200)}
