{generate_api_header(/scheduled_messages:post)}

## Usage examples

{start_tabs}

{generate_code_example(python)|/scheduled_messages:post|example}

{generate_code_example(javascript)|/scheduled_messages:post|example}

{tab|curl}

``` curl
# Create a scheduled stream message
curl -X POST {{ api_url }}/v1/scheduled_messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    --data-urlencode type=stream \
    --data-urlencode to=9 \
    --data-urlencode topic=Hello \
    --data-urlencode 'content=Nice to meet everyone!' \
    --data-urlencode scheduled_delivery_timestamp=3165826990

# Create a scheduled direct message
curl -X POST {{ api_url }}/v1/messages \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    --data-urlencode type=direct \
    --data-urlencode 'to=[9, 10]' \
    --data-urlencode 'content=Can we meet on Monday?' \
    --data-urlencode scheduled_delivery_timestamp=3165826990

```

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/scheduled_messages:post}

{generate_parameter_description(/scheduled_messages:post)}

## Response

{generate_return_values_table|zulip.yaml|/scheduled_messages:post}

{generate_response_description(/scheduled_messages:post)}

#### Example response(s)

{generate_code_example|/scheduled_messages:post|fixture}
