# Update display settings

{generate_api_description(/settings/display:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/settings/display:patch|example}

{tab|curl}

{generate_code_example(curl, include=["left_side_userlist", "emojiset"])|/settings/display:patch|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/settings/display:patch}

## Response

#### Return values

The server will return the settings that have been changed after the request,
with their new value. Please note that this doesn't necessarily mean that it
will return all the settings passed as parameters in the request, but only
those ones that were different from the already existing setting.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/settings/display:patch|fixture(200)}
