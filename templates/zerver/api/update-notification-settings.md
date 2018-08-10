# Update notification settings

Modify the user's preferences for notifications.

`PATCH {{ api_url }}/v1/settings/notifications`

## Usage examples

<div class="code-section" markdown="1">
<ul class="nav">
<li data-language="python">Python</li>
<li data-language="curl">curl</li>
</ul>
<div class="blocks">

<div data-language="curl" markdown="1">

```
curl -X PATCH {{ api_url }}/v1/settings/notifications \
    -u BOT_EMAIL_ADDRESS:BOT_API_KEY \
    -d "enable_stream_desktop_notifications=true" \
    -d "enable_stream_email_notifications=true" \
    -d "enable_stream_push_notifications=true" \
    -d "enable_stream_sounds=true" \
    -d "enable_desktop_notifications=true" \
    -d "enable_sounds=true" \
    -d "enable_offline_email_notifications=true" \
    -d "enable_offline_push_notifications=true" \
    -d "enable_online_push_notifications=true" \
    -d "enable_digest_emails=true" \
    -d "message_content_in_email_notifications=true"
```

</div>

<div data-language="python" markdown="1">

{generate_code_example(python)|/settings/notifications:patch|example}

</div>

</div>

</div>

## Arguments

{generate_api_arguments_table|zulip.yaml|/settings/notifications:patch}

## Response

#### Return values

The server will return the settings that have been changed after the request,
with their new value. Please note that this doesn't necessarily mean that it
will return all the settings passed as parameters in the request, but only
those ones that were different than the already existing setting.

#### Example response

A typical successful JSON response may look like:

{generate_code_example|/settings/notifications:patch|fixture(200)}
