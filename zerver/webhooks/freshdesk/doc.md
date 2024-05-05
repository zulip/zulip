See customer support interactions in Zulip with our Freshdesk
integration!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

### Add notifications for new Freshdesk tickets

1. Go to your Freshdesk **Admin** page. Under **Helpdesk Productivity**,
   click on **Dispatch'r**. Click on **New rule**.

1. Set **Rule Name** to a name of your choice, such as `Zulip`. There isn't a shortcut
   for "always generate a notification on ticket creation", so we'll have to
   fake it by picking two complementary conditions: when the source **is email**,
   and when the source **is not email**. Set up the **Conditions** for the
   new rule, like so:

    ![](/static/images/integrations/freshdesk/001.png)

1. Under **Actions**, set the **Select Action** dropdown to **Trigger Webhook**.
   Set **Request Type** to **POST**, and set **Callback URL** to the URL
   constructed above.

1. Check the **Requires Authentication** checkbox. Set **Username** to the email
   of the bot created above, and set **Password** to the bot's API key. Set
   **Encoding** to **JSON** and select the **Advanced** option. Copy and paste
   the following JSON into the **Content** box:

    ```
    {% raw %}
    {"freshdesk_webhook":
        {
            "triggered_event":"{{triggered_event}}",
            "ticket_id":"{{ticket.id}}",
            "ticket_url":"{{ticket.url}}",
            "ticket_type":"{{ticket.ticket_type}}",
            "ticket_subject":"{{ticket.subject}}",
            "ticket_description":"{{ticket.description}}",
            "ticket_status":"{{ticket.status}}",
            "ticket_priority":"{{ticket.priority}}",
            "requester_name":"{{ticket.requester.name}}",
            "requester_email":"{{ticket.requester.email}}"
        }
    }
    {% endraw %}
    ```

    Click **Save**.

### Get notifications for changes to existing tickets

1. Go to your Freshdesk **Admin** page. Under **Helpdesk Productivity**,
   click on **Observer**, and click on **New rule**.

1. Set **Rule Name** to a name of your choice, such as `Zulip`.
   Under **involves any of these events**, create new events as shown below:

    ![](/static/images/integrations/freshdesk/002.png)

1. Unfortunately, there isn't a shortcut for specifying "all tickets",
   so we'll have to fake it by picking two complementary conditions:
   when the source **is email**, and when the source **is not email**.
   Under **on tickets with these properties**, create new conditions,
   like so:

    ![](/static/images/integrations/freshdesk/003.png)

1. Under **perform these actions**, set the **Select Action** dropdown
   to **Trigger Webhook**. Set **Request Type** to **POST**, and set
   **Callback URL** to the URL constructed above.

1. Check the **Requires Authentication** checkbox. Set **Username** to the email
   of the bot created above, and set **Password** to the bot's API key. Set
   **Encoding** to **JSON** and select the **Advanced** option. Copy and paste
   the following JSON into the **Content** box:

    ```
    {% raw %}
    {"freshdesk_webhook":
        {
            "triggered_event":"{{triggered_event}}",
            "ticket_id":"{{ticket.id}}",
            "ticket_url":"{{ticket.url}}",
            "ticket_type":"{{ticket.ticket_type}}",
            "ticket_subject":"{{ticket.subject}}",
            "ticket_description":"{{ticket.description}}",
            "ticket_status":"{{ticket.status}}",
            "ticket_priority":"{{ticket.priority}}",
            "requester_name":"{{ticket.requester.name}}",
            "requester_email":"{{ticket.requester.email}}"
        }
    }
    {% endraw %}
    ```

    Click **Save**.

{!congrats.md!}

![](/static/images/integrations/freshdesk/004.png)
