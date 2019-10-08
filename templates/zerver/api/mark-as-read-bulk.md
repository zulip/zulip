# Mark all messages as read

Marks all of the current user's unread messages as read.

`POST {{ api_url }}/v1/mark_all_as_read`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/mark_all_as_read:post|example}

{tab|curl}

```
curl -X POST {{ api_url }}/v1/mark_all_as_read \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/mark_all_as_read:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/mark_all_as_read:post|fixture(200)}


# Mark messages in a stream as read

Mark all the unread messages in a stream as read.

`POST {{ api_url }}/v1/mark_stream_as_read`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/mark_stream_as_read:post|example}

{tab|curl}

```
curl -X POST {{ api_url }}/v1/mark_stream_as_read \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "stream_id=42"
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/mark_stream_as_read:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/mark_stream_as_read:post|fixture(200)}


# Mark messages in a topic as read

Mark all the unread messages in a topic as read.

`POST {{ api_url }}/v1/mark_topic_as_read`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/mark_topic_as_read:post|example}

{tab|curl}

```
curl -X POST {{ api_url }}/v1/mark_topic_as_read \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "stream_id=42" \
    -d "topic_name=new coffee machine"
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/mark_topic_as_read:post}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/mark_topic_as_read:post|fixture(200)}
