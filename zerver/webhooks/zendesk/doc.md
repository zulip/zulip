# Zulip Zendesk integration

Get notifications about Zendesk tickets in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Append `{%raw%}&ticket_title={{ ticket.title }}&ticket_id={{ ticket.id }}{%endraw%}`
   to the URL generated above.

1. In Zendesk, click the **gear** (<i class="fa fa-cog"></i>) icon in the
    bottom-left corner. Click on **Extensions**, and then click **add
    target**.

1. Click the **URL target**, and fill in the form with the following:

    * **Title**: Zulip
    * **URL**: the URL generated and updated above
    * **Method**: POST
    * **Attribute Name**: message
    * **Username**: your bot's user name, e.g., `zendesk-bot@yourdomain.com`
    * **Password**: your bot's API key

1. Select **Test Target**, and click **Submit**. A test message should
   appear Zulip. Save the target by selecting **Create target**, and
   clicking **Submit**.

1. Add a new trigger, for every action you'd like to be notified about.
   To add a trigger, select **Triggers** in the left menu, and click
   **add trigger**.

1. Give the trigger a descriptive title (e.g., "Announce ticket update").
   Under **Meet all of the following conditions**, select the conditions
   for the trigger. In the **Perform these actions** section, select
   **Notification: Notify target**, and select the target created above
   (e.g., "Zulip").

1. Enter the message body into the **Message** field. You can use both
   Zulip Markdown and Zendesk placeholders. Here's an example message
   body template that you can optionally use:

        {% raw %}Ticket [#{{ ticket.id }}: {{ ticket.title }}]({{ ticket.link }}), was updated by {{ current_user.name }}
        * Status: {{ ticket.status }}
        * Priority: {{ ticket.priority }}
        * Type: {{ ticket.ticket_type }}
        * Assignee: {{ ticket.assignee.name }}
        * Tags: {{ ticket.tags }}
        * Description:
        ``` quote
        {{ ticket.description }}
        ```{% endraw %}

1.  Click **Submit**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/zendesk/001.png)

### Related documentation

{!webhooks-url-specification.md!}
