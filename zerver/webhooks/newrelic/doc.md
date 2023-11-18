# New Relic ClickUp integration

New Relic can send messages to a Zulip channel for incidents.

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Login to New Relic, go to the **Alerts** menu, and select **Destinations**.
   Choose **Webhook** in the **Add a destination** section.

1. Set a **Webhook name**, such as `Zulip`. Set the **Endpoint URL** to
   the URL generated above. Click **Save destination**.

1. Still in the **Alerts** menu, select **Workflows**. Click on
   **+ Add a Workflow** button.

1. Set your workflow name, and filter the trigger conditions. In the
   **Notify** section, choose **Webhook**.

1. Once the **Edit notification message** menu pops up, select the
   destination for Zulip you've just created earlier.

1. Next, in the **Payload** section you can configure the payload for
   this workflow. Although the out-of-the-box payload template is already
   sufficient to get the integration working, using this message template
   will enable the integration to notify you of any **acknowledged**
   New relic incidents:

         {
            {% raw %}
            "id": {{ json issueId }},
            "issueUrl": {{ json issuePageUrl }},
            "title": {{ json annotations.title.[0] }},
            "priority": {{ json priority }},
            "impactedEntities": {{json entitiesData.names}},
            "totalIncidents": {{json totalIncidents}},
            "state": {{ json state }},
            "trigger": {{ json triggerEvent }},
            "isCorrelated": {{ json isCorrelated }},
            "createdAt": {{ createdAt }},
            "closedAt": {{ json closedAt }},
               "updatedAt": {{ updatedAt }},
               "sources": {{ json accumulations.source }},
               "alertPolicyNames": {{ json accumulations.policyName }},
               "alertConditionNames": {{ json accumulations.conditionName }},
               "workflowName": {{ json workflowName }},
            "acknowledgedAt": {{ json acknowledgedAt }},
            "acknowedgedBy":{{ json acknowledgedBy }},
            "owner": {{ json owner }},
            "zulipCustomFields": {}
            {% endraw %}
         }
   You can copy and past this template as is to the **Template** box in the
   **Payload** section. And if you want to include more custom fields, refer to the
   [this](#include-custom-fields-in-your-notifications) section.

1. Additionally, at this point you can try and test the integration by clicking
   the **Send test notification**.

1. Finally, select **Save message** and then click **Activate Workflow** to
   complete the integration.



{end_tabs}

{!congrats.md!}

![](/static/images/integrations/newrelic/001.png)

### Include custom fields in your notifications.

With New Relic's [custom payload feature][custom-payload], you can
include custom fields in your Zulip notifications by configuring a
`zulipCustomFields` dictionary in your notification payload template.

The keys of `zulipCustomFields` will be displayed in the Zulip
notification message, so we recommend that they be human-readable
and descriptive. The values of the dictionary can be strings, integers,
booleans, or lists of the those same data types.

  *example payload with custom fields:*

      {
         {% raw %}
         "id": {{ json issueId }},

         ...

         "zulipCustomFields": {
            "Your Custom Payload": {{ json exampleField }},
            "Storage Hardware": {{ json exampleList }},
            "Closed Count": {{ json closedIncidentsCount }}
         }
         {% endraw %}
      }

### Related documentation

- [**New relic notification integrations documentation**](https://docs.newrelic.com/docs/alerts/get-notified/notification-integrations/#set-webhook-destination)

- [**New relic workflows documentation**](https://docs.newrelic.com/docs/alerts-applied-intelligence/applied-intelligence/incident-workflows/incident-workflows/)

- [**New relic destinations documentation**](https://docs.newrelic.com/docs/alerts/get-notified/destinations/)

- [**New relic integration message template documentation**][custom-payload]

{!webhooks-url-specification.md!}

[custom-payload]: https://docs.newrelic.com/docs/alerts-applied-intelligence/notifications/message-templates/
