# Zulip Freshdesk integration

See customer support interactions in Zulip with our Freshdesk
integration!

### Create Zulip bot for Freshdesk notifications

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

{end_tabs}


### Add notifications for new Freshdesk tickets

{start_tabs}

1. Go to your Freshdesk **Admin** page.

1. Under **Helpdesk Productivity**, select **Dispatch'r**, and then
   select **New rule**.

1. Set **Rule Name** to a name of your choice, such as `Zulip`.

1. There isn't a shortcut to "always generate a notification on ticket
   creation", so we'll have to fake it by picking two complementary
   conditions: when the source **is email**, and when the source **is
   not email**. Set up the **Conditions** for the new rule, like so:

     ![](/static/images/integrations/freshdesk/001.png)

1. Under **Actions**, set the **Select Action** dropdown to **Trigger
   Webhook**.

1. Set **Request Type** to **POST**, and set **Callback URL** to the URL
   [generated above][create-bot].

1. Toggle the **Requires Authentication** checkbox.

1. Set **Username** to the email of the bot [created above][create-bot],
   and set **Password** to the bot's API key.

1. Set **Encoding** to **JSON**, and select the **Advanced** option.
   Copy and paste the following JSON into the **Content** box:

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

1. Click **Save**.

{end_tabs}

### Get notifications for changes to existing Freshdesk tickets

{start_tabs}

1. Go to your Freshdesk **Admin** page.

1. Under **Helpdesk Productivity**, select **Observer**, and then select
   **New rule**.

1. Set **Rule Name** to a name of your choice, such as `Zulip`.

1. Under **involves any of these events**, create new events as shown below:

    ![](/static/images/integrations/freshdesk/002.png)

1. Unfortunately, there isn't a shortcut for specifying "all tickets",
   so we'll have to fake it by picking two complementary conditions:
   when the source **is email**, and when the source **is not email**.
   Under **on tickets with these properties**, create new conditions,
   like so:

    ![](/static/images/integrations/freshdesk/003.png)

1. Under **perform these actions**, set the **Select Action** dropdown
   to **Trigger Webhook**.

1. Set **Request Type** to **POST**, and set **Callback URL** to the URL
   [generated above][create-bot].

1. Toggle the **Requires Authentication** checkbox.

1. Set **Username** to the email of the bot [created above][create-bot],
   and set **Password** to the bot's API key.

1. Set **Encoding** to **JSON** and select the **Advanced** option.
   Copy and paste the following JSON into the **Content** box:

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

1. Select **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/freshdesk/004.png)

### Related documentation

{!webhooks-url-specification.md!}

[create-bot]: #create-zulip-bot-for-freshdesk-notifications
