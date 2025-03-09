# Zulip Zendesk integration

Get notifications about Zendesk tickets in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Head over to the [Admin Center](https://support.zendesk.com/hc/en-us/articles/4581766374554-Using-Zendesk-Admin-Center#topic_hfg_dyz_1hb) for your Zendesk account.

1. In the left sidebar, navigate to `Apps and Integrations`->`Actions and webhooks`->`Webhooks` or head over to `https://<your_subdomain>.zendesk.com/admin/apps-integrations/actions-webhooks/webhooks`.

1. Click on `Create Webhook`.

1. Select the `Trigger or Automation` option and click `Next`.

1. In the details section, set the **Request method** to `POST`, **Request format** to `JSON` and enter the webhook URL generated previously in the **Endpoint URL** field.

1. Select `Basic Authentication` in the **Authentication** options and enter your Zulip Bot email for the **Username** and Zulip Bot API KEY for the **Password**.

1. Head over to `https://<your_subdomain>.zendesk.com/agent/admin/triggers` and select the `Create Trigger` option.

1. Select `Notifications` for the **Trigger Category**.
1. Add the two conditions below in **Meet ANY of the following conditions**:
      - Category: `Ticket > Ticket`, Operator: `IS`, Value: `Created`
      - Category: `Ticket > Ticket`, Operator: `IS`, Value: `Updated`
1. In the **Actions** section add an action having:

      Category: `Notify by > Active webhook`, Value: `<Your_webhook_name>`

1. Enter the message body into the **message** field of the JSON object. You can use both
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

1. Additionally you can also provide the `topic` field to get notifications in a custom topic.

1. To get notifications for a given ticket in its own dedicated topic, add the fields
`{% raw %}ticket_id:{{ticket.id}}{% endraw %}`
and
`{% raw %}ticket_title:{{ticket.title}}{% endraw %}`


1. Click on `Create Trigger` to add the new trigger.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/zendesk/001.png)

### Related documentation

- [Zendesk webhook documentation](https://support.zendesk.com/hc/en-us/articles/4408839108378-Creating-webhooks-to-interact-with-third-party-systems)
{!webhooks-url-specification.md!}
