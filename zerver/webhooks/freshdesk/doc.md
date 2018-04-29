See customer support interactions in Zulip with our Freshdesk
integration!

**Note**: This integration must be set up by an administrator
for your Freshdesk instance.

The setup process is different for setting up Zulip notifications
for new Freshdesk tickets and setting up notifications for
changes to existing tickets. The setup process is divided into the
following two parts.

### Part 1: Zulip notifications for new Freshdesk tickets

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to your Freshdesk **Admin** page. Under **Helpdesk Productivity**,
   click on **Dispatch'r**, and click on **New rule**.

1. Set **Rule Name** to a name of your choice, such as `Zulip`. Optionally,
   you may also provide a description. Unfortunately, there isn't a shortcut
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
    {"freshdesk_webhook":
        {
            "triggered_event":"&#123;&#123;triggered_event&#125;&#125;",
            "ticket_id":"&#123;&#123;ticket.id&#125;&#125;",
            "ticket_url":"&#123;&#123;ticket.url&#125;&#125;",
            "ticket_type":"&#123;&#123;ticket.ticket_type&#125;&#125;",
            "ticket_subject":"&#123;&#123;ticket.subject&#125;&#125;",
            "ticket_description":"&#123;&#123;ticket.description&#125;&#125;",
            "ticket_status":"&#123;&#123;ticket.status&#125;&#125;",
            "ticket_priority":"&#123;&#123;ticket.priority&#125;&#125;",
            "requester_name":"&#123;&#123;ticket.requester.name&#125;&#125;",
            "requester_email":"&#123;&#123;ticket.requester.email&#125;&#125;",
        }
    }
    ```

    Finally, click **Save**. The next time a Freshdesk ticket is opened,
    you will get a notification in Zulip!

!!! tip ""

    If you only want to receive Zulip notifications on ticket creation,
    stop here, you're done! If you also want to receive notifications
    when changes are made to existing tickets, please continue on to
    **Part 2**.

### Part 2: Zulip notifications for changes to existing tickets

If you've already created a stream and a bot for this integration
in **Part 1** of the setup, you may skip the first two steps!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to your Freshdesk **Admin** page. Under **Helpdesk Productivity**,
   click on **Observer**, and click on **New rule**.

1. Set **Rule Name** to a name of your choice, such as `Zulip`. Optionally,
   you may also provide a description. Under **involves any of these events**,
   create new events as shown below:

    ![](/static/images/integrations/freshdesk/002.png)

    If you do not wish to receive Zulip notifications for one of these
    events, you may choose to leave them out.

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
    {"freshdesk_webhook":
        {
            "triggered_event":"&#123;&#123;triggered_event&#125;&#125;",
            "ticket_id":"&#123;&#123;ticket.id&#125;&#125;",
            "ticket_url":"&#123;&#123;ticket.url&#125;&#125;",
            "ticket_type":"&#123;&#123;ticket.ticket_type&#125;&#125;",
            "ticket_subject":"&#123;&#123;ticket.subject&#125;&#125;",
            "ticket_description":"&#123;&#123;ticket.description&#125;&#125;",
            "ticket_status":"&#123;&#123;ticket.status&#125;&#125;",
            "ticket_priority":"&#123;&#123;ticket.priority&#125;&#125;",
            "requester_name":"&#123;&#123;ticket.requester.name&#125;&#125;",
            "requester_email":"&#123;&#123;ticket.requester.email&#125;&#125;",
        }
    }
    ```

    Finally, click **Save**. The next time a Freshdesk ticket is updated,
    you will get a notification in Zulip!

{!congrats.md!}

![](/static/images/integrations/freshdesk/004.png)
