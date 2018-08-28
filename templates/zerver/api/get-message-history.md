# Get a message's history

Get the different versions of a previously edited message.

`GET {{ api_url }}/v1/messages/<message_id>/history`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl {{ api_url }}/v1/messages/<message_id>/history \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/messages/{message_id}/history:get|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/messages/{message_id}/history:get}

## Response

#### Return values

* `message_history`: a chronologically sorted array of `snapshot` objects,
    each one with the values of the message after the edition.
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

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/messages/{message_id}/history:get|fixture(200)}

An example JSON response for when the specified message does not exist:

{generate_code_example|/messages/{message_id}/history:get|fixture(400)}
