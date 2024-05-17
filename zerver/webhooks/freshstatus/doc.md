Receive Freshstatus notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. On your Freshstatus dashboard, click **Settings** and click **Integrations**.
   Go to **Webhooks** and click **Manage**. Click **New Webhook**
   to set up a new webhook.

1. Set **Webhook Name** to any name of your choice, such as `Zulip`.
   Set **Description** to any suitable description.

1. Under **Condition**, select the events you would like to be notified for.
   Under **Action**, set **Request Type** to `POST`. Set **Callback URL**
   to the **URL** constructed above.

1. Leave **Requires Authentication** unchecked and set **Content** to
   **Advanced**.

1. Set **Incident JSON** to the following:

      ```
      {
         "id": "{id}",
         "title": "{title}",
         "description": "{description}",
         "start_time": "{start_time}",
         "end_time": "{end_time}",
         "is_private": "{is_private}",
         "source": "{source}",
         "affected_services": "{affected_services}",
         "notification_options": "{notification_options}"
      }
      ```

1. Set **Maintenance JSON** to the following:

      ```
      {
         "id": "{id}",
         "title": "{title}",
         "description": "{description}",
         "start_time": "{start_time}",
         "end_time": "{end_time}",
         "is_private": "{is_private}",
         "source": "{source}",
         "affected_services": "{affected_services}",
         "notification_options": "{notification_options}",
         "scheduled_start_time": "{scheduled_start_time}",
         "scheduled_end_time": "{scheduled_end_time}",
         "is_auto_update_status_on_scheduled_start": "{is_auto_update_status_on_scheduled_start}",
         "is_auto_update_status_on_scheduled_end": "{is_auto_update_status_on_scheduled_end}",
         "is_auto_update_component_status_on_scheduled_start": "{is_auto_update_component_status_on_scheduled_start}",
         "is_auto_update_component_status_on_scheduled_end": "{is_auto_update_component_status_on_scheduled_end}"
      }
      ```

1. Set **Incident/Maintenance Note JSON** to the following:

      ```
      {
         "id": "{note_id}",
         "title": "{title}",
         "incident_id": "{note_incident_id}",
         "incident_status": "{note_incident_status}",
         "message": "{note_message}",
         "status": "{note_status}",
         "is_private": "{note_is_private}",
         "notification_options": "{note_notification_options}"
      }
      ```

1. Finally, click **Save**. Optionally, you may click **Test** to check if
   the webhook was configured correctly.

{!congrats.md!}

![](/static/images/integrations/freshstatus/001.png)
