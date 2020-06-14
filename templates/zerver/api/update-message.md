# Edit a message

{generate_api_description(/messages/{message_id}:patch)}

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}:patch|example}

{tab|js}

More examples and documentation can be found [here](https://github.com/zulip/zulip-js).

{generate_code_example(javascript)|/messages/{message_id}:patch|example}

{tab|curl}

{generate_code_example(curl, exclude=["stream_id"])|/messages/{message_id}:patch|example}

{end_tabs}

## Permissions

You only have permission to edit a message if:

1. You sent it, **OR**:
2. This is a topic-only edit for a (no topic) message, **OR**:
3. This is a topic-only edit and you are an admin, **OR**:
4. This is a topic-only edit and your realm allows users to edit topics.

## Parameters

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}:patch}

## Response

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}:patch|fixture(200)}

A typical JSON response for when one doesn't have the permission to
edit a particular message:

{generate_code_example|/messages/{message_id}:patch|fixture(400)}
