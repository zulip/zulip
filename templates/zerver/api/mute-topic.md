# Topic muting

{generate_api_description(/users/me/subscriptions/muted_topics:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/users/me/subscriptions/muted_topics:patch|example}

{tab|curl}

{generate_code_example(curl, exclude=["stream_id"])|/users/me/subscriptions/muted_topics:patch|example}

{end_tabs}

## Parameters

{generate_api_arguments_table|zulip.yaml|/users/me/subscriptions/muted_topics:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/users/me/subscriptions/muted_topics:patch|fixture(200)}


An example JSON response for when an `add` operation is requested for a topic
that has already been muted:

{generate_code_example|/users/me/subscriptions/muted_topics:patch|fixture(400_0)}

An example JSON response for when a `remove` operation is requested for a
topic that had not been previously muted:

{generate_code_example|/users/me/subscriptions/muted_topics:patch|fixture(400_1)}
