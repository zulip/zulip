# Delete User Group

Delete user group

`DELETE {{ api_url }}/v1/user_groups/{group_id}`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups/{group_id}:delete|example}

{tab|curl}

``` curl
curl -X DELETE {{ api_url }}/v1/user_groups/{group_id} \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'group_id=2'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/user_groups/{group_id}:delete}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups/{group_id}:delete|fixture(200)}

An example JSON response when group id given does not exist:

{generate_code_example|/user_groups/{group_id}:delete|fixture(400)}
