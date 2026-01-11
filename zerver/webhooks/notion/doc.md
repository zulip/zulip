# Notion

This integration allows you to receive notifications from Notion via their Automation or API webhooks.

## Setup

1. In Zulip, create a **Notion** bot to get the webhook URL.
2. In Notion, use **Automations** (or a helper service like Zapier/Make, or a custom script) to send a JSON POST request to the Zulip URL.
3. The JSON payload should be structured as follows:

```json
{
    "event": "Page Created",
    "title": "Page Title",
    "url": "https://www.notion.so/page-url"
}
```

The `event` field will be used as the topic, and the `title`/`url` will form the message body.
