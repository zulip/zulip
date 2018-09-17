# Get a message's edit history

Fetch the message edit history of a previously edited message.

`GET {{ api_url }}/v1/messages/<message_id>/history`

Note that edit history may be disabled in some organizations; see the
[Zulip Help Center documentation on editing messages][edit-settings].

[edit-settings]: /help/view-a-messages-edit-history

## Usage examples

{start_tabs}
{tab|python}

{generate_code_example(python)|/messages/{message_id}/history:get|example}

{tab|curl}

```
curl {{ api_url }}/v1/messages/<message_id>/history \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

{end_tabs}

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}/history:get}

## Response

#### Return values

* `message_history`: a chronologically sorted array of `snapshot` objects,
    containing the modified state of the message before and after the edit:
    * `topic`: the topic for the message.
    * `content`: the body of the message.
    * `rendered_content`: the already rendered, HTML version of `content`.
    * `prev_content`: the body of the message before being edited.
    * `prev_rendered_content`: the already rendered, HTML version of
        `prev_content`.
    * `user_id`: the ID of the user that made the edit.
    * `content_html_diff`: an HTML diff between this version of the message
        and the previous one.
    * `timestamp`: the UNIX timestamp for this editi.

Please note that the original message's snapshot only contains the fields
`topic`, `content`, `rendered_content`, `timestamp` and `user_id`. This
snapshot will be the only one present if the message has never been edited.

Also note that if a message's content was edited (but not the topic)
or the topic was edited (but not the content), the snapshot object
will only contain data for the modified fields (e.g. if only the topic
was edited, `prev_content`, `prev_rendered_content`, and
`content_html_diff` will not appear).

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}/history:get|fixture(200)}

An example JSON response for when the specified message does not exist:

{generate_code_example|/messages/{message_id}/history:get|fixture(400)}
