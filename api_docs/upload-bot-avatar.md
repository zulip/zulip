# Upload a bot avatar

{generate_api_header(/bots/{bot_id}/avatar:post)}

Upload and set a new avatar image for a bot user.

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/bots/{bot_id}/avatar:post|example}

{tab|curl}

{generate_code_example(curl)|/bots/{bot_id}/avatar:post|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/bots/{bot_id}/avatar:post}

## Response

#### Return values

* `avatar_url`: The URL of the uploaded avatar image.

#### Example response(s)

{generate_code_example|/bots/{bot_id}/avatar:post|fixture(200)}
