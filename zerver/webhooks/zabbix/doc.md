Receive Zabbix notifications in Zulip!

!!! warn ""

    **Note:** This guide is for Zabbix 5.4 and above; some older Zabbix versions have a
    different workflow for creating an outgoing webhook.

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Go to your Zabbix web interface, and click **Administration**. Click on
   **General** and then select **Macros** from the dropdown. Click **Add** and set the
   macro to `{$ZABBIX_URL}`. Set the value as the URL to your Zabbix server like
   `https://zabbix.example.com` ensuring there no trailing slashes. Click **Update**

1. Go back to your Zabbix web interface, and click **Administration**. Click on
   **Media Types**, and click **Create Media Type**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set **Type** to **Webhook**.
   Add the following **Parameters**:

    * Add `hostname` as the first parameter with the value `{HOST.NAME}`.
    * Add `item` as the second parameter with the value `{ITEM.NAME1} is {ITEM.VALUE1}`.
    * Add `link` as the third parameter with the value `{$ZABBIX_URL}/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}`.
    * Add `severity` as the fourth parameter with the value `{TRIGGER.SEVERITY}`.
    * Add `status` as the fifth parameter with the value `{TRIGGER.STATUS}`.
    * Add `trigger` as the sixth parameter with the value `{TRIGGER.NAME}`.
    * Add `zulip_endpoint` as the seventh parameter with the value set as the URL
      constructed earlier.

1. Click the **Pencil** to edit the script and replace any existing content with the below script:

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

1. Check the **Enabled** option.

1. Click **Message Templates** in the top bar. Click **Add** under **Message Type**. Select **Problem**.

1. Set **Subject** to `{TRIGGER.STATUS}-{TRIGGER.SEVERITY}-{TRIGGER.NAME}`.
   Set **Message** to the following:

         {
         "hostname": "{HOST.NAME}",
         "severity": "{TRIGGER.SEVERITY}",
         "status": "{TRIGGER.STATUS}",
         "item": "{ITEM.NAME1} is {ITEM.VALUE1}",
         "trigger": "{TRIGGER.NAME}",
         "link": "{$ZABBIX_URL}/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}"
         }

1. Click **Add**.

1. Go back to your Zabbix web interface, and click **Administration**.
   Click on **Users**, and select the alias of the user you would like
   to use to set the notification. Click **Media**, and click **Add**.

1. Set **Type** to **Zulip** or whatever you named your media type as.
   Set **Send To** to `Zulip` or any text. This field needs something in,
   but isn't used. Tweak the severity and times when active for notifications
   as appropriate, and check the **Enabled** option. Click **Add**.
   Click **Update**.

1. Go back to your Zabbix web interface, and click **Configuration**.
   Click **Actions**, and click **Create Action**.

1. Set **Name** to a name of your choice, such as `Zulip`. Under
   **New Conditions**, add the conditions for triggering a notification.
   Check the **Enabled** option, and click **Operations**.

1. Under **Operations** click **Add**, and then set **Operation Type** to
   `Send Message`. Under **Send to Users**, click **Add**, and select the user
   you added the alert to and click **Select**. Under **Send only to**,
   select **Zulip** or the name of your media type. Click **Add**  twice.

{!congrats.md!}

![](/static/images/integrations/zabbix/001.png)
