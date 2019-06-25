# Update User Group

Update user group

`PATCH {{ api_url }}/v1/user_groups/{group_id}`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/user_groups/{group_id}:patch|example}

{tab|curl}

``` curl
curl -X PATCH {{ api_url }}/v1/user_groups/{group_id} \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'group_id=2' \
    -d 'name="Manchester United"' \
    -d 'description="Biggest club in the world."'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/user_groups/{group_id}:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/user_groups/{group_id}:patch|fixture(200)}

An example JSON response when the given group ID does not exist:

{generate_code_example|/user_groups/{group_id}:patch|fixture(400)}
