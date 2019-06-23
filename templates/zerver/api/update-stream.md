# Update stream

Configure the stream with the ID `stream_id`.  This endpoint supports
an organization administrator editing any property of a stream,
including:

* Stream [name](/help/rename-a-stream) and [description](/help/change-the-stream-description)
* Stream [permissions](/help/stream-permissions), including
  [privacy](/help/change-the-privacy-of-a-stream) and [who can
  send](/help/announcement-only-streams).

`PATCH {{ api_url }}/v1/streams/{stream_id}`

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/streams/{stream_id}:patch|example}

{tab|curl}

``` curl
curl -X PATCH {{ api_url }}/v1/streams/{stream_id} \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d 'new_name="Manchester United"' \
    -d 'description="Biggest club in the world"' \
    -d 'is_private=false'
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/streams/{stream_id}:patch}

## Response

#### Return values

* `stream_id`: The ID of the stream to be updated.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/streams/{stream_id}:patch|fixture(200)}

An example JSON response for when the supplied stream does not exist:

{generate_code_example|/streams/{stream_id}:patch|fixture(400)}
