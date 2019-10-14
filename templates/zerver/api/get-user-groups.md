# Get user groups

{!api-members-only.md!}

Fetches all of the user groups in the organization.

`GET {{ api_url }}/v1/user_groups`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups:get|example}

{tab|curl}

{generate_code_example(curl)|/user_groups:get|example}

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/user_groups:get}

## Response

#### Return values

* `user_groups`: A list of dictionaries, where each dictionary contains information
  about a user group.
    * `description`: The human-readable description of the user group.
    * `id`: The user group's integer id.
    * `members`: The integer User IDs of the user group members.
    * `name`: User group name.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups:get|fixture(200)}
