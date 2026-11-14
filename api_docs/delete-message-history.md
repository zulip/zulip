{generate_api_header(/messages/{message_id}/history:delete)}

## Usage examples

{start_tabs}

{generate_code_example(python)|/messages/{message_id}/history:delete|example}

{tab|curl}

{!curl-auth-credentials.md!}
```curl
curl -sSX DELETE {{ api_url }}/v1/messages/MESSAGE_ID/history \
    -u EMAIL_ADDRESS:API_KEY
```

{end_tabs}

## Parameters

{generate_api_parameter_description(/messages/{message_id}/history:delete)}

## Response

#### Return values

{generate_return_values(/messages/{message_id}/history:delete)}

#### Example response(s)

{generate_code_example(python)|/messages/{message_id}/history:delete|fixture}
