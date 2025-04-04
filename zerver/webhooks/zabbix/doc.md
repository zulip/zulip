# Zulip Zabbix integration

Receive Zabbix notifications in Zulip!

!!! warn ""

    **Note:** This guide is for Zabbix 5.4 and above; some older Zabbix
    versions have a different workflow for creating an outgoing webhook.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to **Administration** in your Zabbix web interface. Click on
   **General**, and select **Macros** from the dropdown. Click **Add**.

1. Set the macro to `{$ZABBIX_URL}`. Set the value as the URL to your
   Zabbix server, e.g., `https://zabbix.example.com`, and ensure that there
   are no trailing slashes. Click **Update**.

1. Go back to **Administration** in your Zabbix web interface. Select
   **Media Types**, and click **Create Media Type**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set **Type** to
   **Webhook**, and add the following **Parameters**:

    * `hostname`: `{HOST.NAME}`
    * `item`: `{ITEM.NAME1} is {ITEM.VALUE1}`
    * `link`: `{$ZABBIX_URL}/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}`
    * `severity`: `{TRIGGER.SEVERITY}`
    * `status`: `{TRIGGER.STATUS}`
    * `trigger`: `{TRIGGER.NAME}`
    * `zulip_endpoint`: the URL generated above

1. Click the **Pencil** to edit the script, and replace any existing content
   with the script below. Then, check the **Enabled** option.

         try {
            Zabbix.Log(4, 'zulip webhook script value='+value);

            var result = {
               'tags': {
                     'endpoint': 'zulip'
               }
            },
            params = JSON.parse(value),
            req = new HttpRequest(),
            payload = {},
            resp;

            req.addHeader('Content-Type: application/json');

            payload.hostname = params.hostname;
            payload.severity = params.severity;
            payload.status = params.status;
            payload.item = params.item;
            payload.trigger = params.trigger;
            payload.link = params.link;
            resp = req.post(params.zulip_endpoint,
               JSON.stringify(payload))

            if (req.getStatus() != 200) {
               throw 'Response code: '+req.getStatus();
            }

            resp = JSON.parse(resp);
            result.tags.issue_id = resp.id;
            result.tags.issue_key = resp.key;
         } catch (error) {
            Zabbix.Log(4, 'zulip issue creation failed json : '+JSON.stringify(payload));
            Zabbix.Log(4, 'zulip issue creation failed : '+error);

            result = {};
         }

         return JSON.stringify(result);

1. Open **Message Templates** from the top bar. Click **Add** under **Message Type**,
   and select **Problem**.

1. Set **Subject** to `{TRIGGER.STATUS}-{TRIGGER.SEVERITY}-{TRIGGER.NAME}`.
   Set **Message** to the following, and click **Add**:

         {
            "hostname": "{HOST.NAME}",
            "severity": "{TRIGGER.SEVERITY}",
            "status": "{TRIGGER.STATUS}",
            "item": "{ITEM.NAME1} is {ITEM.VALUE1}",
            "trigger": "{TRIGGER.NAME}",
            "link": "{$ZABBIX_URL}/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}"
         }

1. Go back to **Administration** in your Zabbix web interface. Click on
   **Users**, and select the alias of the user you would like to use to
   set the notification. Select **Media**, and click **Add**.

1. Set **Type** to the name you assigned to the media type above.
   Set **Send To** to `Zulip` or any text, as this field requires text, but
   it isn't used. Set the severity and active periods for notifications as
   suitable, and check the **Enabled** option. Click **Add**, and
   select **Update**.

1. Go back to your Zabbix web interface, and click **Configuration**.
   Select **Actions**, and choose **Create Action**.

1. Set **Name** to a name of your choice, such as `Zulip`. Under
   **New Conditions**, add the conditions for triggering a notification.
   Check the **Enabled** option, and click **Operations**.

1. Under **Operations**, click **Add**, and then set **Operation Type** to
   `Send Message`. Under **Send to Users**, choose **Add**, and select the user
   you added the alert to above, and click **Select**. Under **Send only to**,
   select **Zulip** or the name of your media type. Click **Add** twice.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/zabbix/001.png)

### Related documentation

{!webhooks-url-specification.md!}
