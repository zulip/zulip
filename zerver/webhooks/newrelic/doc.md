# Zulip New Relic integration

Get Zulip notification for New Relic incidents.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In New Relic, go to the **Alerts** menu, and select **Destinations**.
   Choose **Webhook** in the **Add a destination** section.

1. Set a **Webhook name**, such as `Zulip`. Set the **Endpoint URL** to
   the URL generated above. Click **Save destination**.

1. In the **Alerts** menu, select **Workflows**. Click on
   **+ Add a Workflow**.

1. Set your workflow name, and filter the trigger conditions. In the
   **Notify** section, choose **Webhook**. In the **Edit notification
   message** menu, select the destination for Zulip created above.

1. In the **Payload** section, you can configure the payload for this
   workflow. The default payload template is sufficient to get the
   integration working, but using the message template below will enable
   the integration to notify you of any **acknowledged** New Relic
   incidents. To include additional custom fields, refer to
   [configuration options](#configuration-options):

         {
            {% raw %}
            "id": {{ json issueId }},
            "issueUrl": {{ json issuePageUrl }},
            "title": {{ json annotations.title.[0] }},
            "priority": {{ json priority }},
            "totalIncidents": {{json totalIncidents}},
            "state": {{ json state }},
            "createdAt": {{ createdAt }},
            "updatedAt": {{ updatedAt }},
            "alertPolicyNames": {{ json accumulations.policyName }},
            "alertConditionNames": {{ json accumulations.conditionName }},
            "owner": {{ json owner }},
            "zulipCustomFields": {}
            {% endraw %}
         }

1. Click **Send test notification** to receive a test notification. Select
   **Save message**, and click **Activate Workflow**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/newrelic/001.png)

### Configuration options

* With New Relic's [custom payload feature][1], you can include custom
  fields in your Zulip notifications by configuring a `zulipCustomFields`
  dictionary in your notification payload template. The keys of
  `zulipCustomFields` will be displayed in the Zulip notification
  message, so we recommend that they be human-readable and descriptive.
  The values of the dictionary can be strings, integers, booleans, or
  lists of the those same data types.

### Related documentation

* [**New Relic webhook integration**][2]

* [**New Relic message templates**][1]

{!webhooks-url-specification.md!}

[1]: https://docs.newrelic.com/docs/alerts-applied-intelligence/notifications/message-templates/
[2]: https://docs.newrelic.com/docs/alerts/get-notified/notification-integrations/#webhook
