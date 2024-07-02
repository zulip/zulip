# New Relic ClickUp integration

New Relic can send messages to a Zulip channel for incidents.

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to the [**Destinations**][destinations] menu and select **Webhook** in
   the **Add a destination** section. ([*Official Guide*][official-guide])

1. Set **Endpoint URL** to the URL you generated.

1. Go to the [**Workflows**][workflows] menu and click on **+ Add a Workflow**
   button. After filtering the trigger condition, select on the **Webhook**
   option in the **Add Channel** section. ([*Workflow doc*][workflow-doc])

1. Once you're in the **Edit notification message** menu, select the
   destination for Zulip you've just created earlier.

1. If you want to include additional information to the notification, refer
   to this [section](#displaying-custom-fields). There's also an
   optional [base payload template](#recommended-base-payload-template) we
   recommend you to use.

1. Select **Save message** and the **Activate Workflow** to finish.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/newrelic/001.png)

![](/static/images/integrations/newrelic/002.png)

### Displaying Custom Fields

The New Relic integration supports the [custom payload feature][custom-payload]
offered by New Relic. To include your custom fields in your Zulip New Relic
notification, follow these rules:

* Put all your custom key-value pairs in a new dictionary called
  `zulipCustomFields`.

* The keys inside the `zulipCustomFields` dict will be displayed
  in the notification message as is, so we recommend you to use
  descriptive and human-readable words for the keys.

* The supported data-type for the custom payload are: `string`, `list`, `int`
  and `bool`. Custom payload containing `dict` are not supported.

  *example payload with custom fields:*

       {
         {% raw %}
         "id": {{ json issueId }},

         ...

         "zulipCustomFields": {
            "Your Custom Payload": "somedata123",
            "Storage Hardware": ["SSD", "HDD],
            "Closed Count": {{ json closedIncidentsCount }}
         }
         {% endraw %}
      }

  *the Zulip notification from the payload above:*
  ![](/static/images/integrations/newrelic/custom_payload_notif.png)

Only custom fields inside the `zulipCustomFields` dictionary will be displayed.

### Recommended Base Payload Template

Although the out-of-the-box payload template is already sufficient to get the
integration working, the additional fields provided from this template will
enable the integration to notify you of any **acknowledged** incidents:

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

   > Note: you can directly copy and paste the template above
### Related documentation

{!webhooks-url-specification.md!}

[destinations]: https://one.newrelic.com/alerts-ai/notify/destinations

[official-guide]: https://docs.newrelic.com/docs/alerts-applied-intelligence/notifications/notification-integrations/#set-webhook-destination

[workflows]: https://one.newrelic.com/alerts-ai/workflows

[workflow-doc]: https://docs.newrelic.com/docs/alerts-applied-intelligence/applied-intelligence/incident-workflows/incident-workflows/

[custom-payload]: https://docs.newrelic.com/docs/alerts-applied-intelligence/notifications/message-templates/
