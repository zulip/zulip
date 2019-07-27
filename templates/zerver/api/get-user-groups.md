# Get user groups

Fetches all of the user groups in the organization.
Note: Only organization members or admins can contact this endpoint.
This means that bots and guests cannot contact this endpoint.

`GET {{ api_url }}/v1/user_groups`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups:get|example}

{tab|curl}

``` curl
curl -X GET {{ api_url }}/v1/user_groups \
    -u USER_EMAIL_ADDRESS:USER_API_KEY
```

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
