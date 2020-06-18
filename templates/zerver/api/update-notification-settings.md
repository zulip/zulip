# Update notification settings

{generate_api_description(/settings/notifications:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/settings/notifications:patch|example}

{tab|curl}

{generate_code_example(curl, include=["enable_offline_push_notifications", "enable_online_push_notifications"])|/settings/notifications:patch|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/settings/notifications:patch}

## Response

#### Return values

The server will return the settings that have been changed after the request,
with their new value. Please note that this doesn't necessarily mean that it
will return all the settings passed as parameters in the request, but only
those ones that were different than the already existing setting.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/settings/notifications:patch|fixture(200)}
