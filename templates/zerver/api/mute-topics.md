# Topic muting

This endpoint mutes/unmutes a topic within a stream that the current
user is subscribed to.  Muted topics are displayed faded in the Zulip
UI, and are not included in the user's unread count totals.

`PATCH {{ api_url }}/v1/users/me/subscriptions/muted_topics`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions/muted_topics:patch|example}

{tab|curl}

```
curl -X PATCH {{ api_url }}/v1/users/me/subscriptions/muted_topics \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "stream=Verona"
    -d "topic=dinner"
    -d "op=add"
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions/muted_topics:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions/muted_topics:patch|fixture(200)}


An example JSON response for when an `add` operation is requested for a topic
that has already been muted:

{generate_code_example|/users/me/subscriptions/muted_topics:patch|fixture(400_topic_already_muted)}

An example JSON response for when a `remove` operation is requested for a
topic that had not been previously muted:

{generate_code_example|/users/me/subscriptions/muted_topics:patch|fixture(400_topic_not_muted)}
