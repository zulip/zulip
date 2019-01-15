Receive Zabbix notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1.  On your Zabbix Server, create a script called `zulip.sh` in the
    `alertscripts` folder with the following contents:

        #!/bin/bash

        webhook_url="$1"

        # Build our JSON payload and send it as a POST request to the Zulip incoming web-hook URL
        payload="$3"
        /usr/bin/curl -m 5 --data "$payload" "${webhook_url}"

    The `alertscripts` folder is usually found under `/usr/lib/zabbix/`, but
    the exact path might differ depending on your environment. Make sure the
    script is executable by your Zabbix environment.

1. Go to your Zabbix Web Interface, and click **Administration**. Click on
   **Media Types**, and click **Create Media Type**.

1. Set **name** to a name of your choice, such as `Zulip`. Set **type** to **Script**,
   and set **Script name** to `zulip.sh`. Add the following **Parameters**:

    * Add `{ALERT.SENDTO}` as the first parameter.
    * Add `{ALERT.SUBJECT}` as the second parameter.
    * Add `{ALERT.MESSAGE}` as the third parameter.

    Check the **Enabled** option, and click **Update**.

1. Go back to your Zabbix Web Interface, and click **Administration**. Click
   on **Users**, and select the alias of the user you would like
   to use to set the notification. Click **Media**, and click **Add**.

1. Set **Type** to **Zulip**, and set **Send To** to the URL constructed.
   Tweak the serverity for notifications as appropriate, and check the
   **Enabled** option.

1. Go back to your Zabbix Web Interface, and click **Configuration**.
   Click **Actions**, and click **Create Action**.

1. Set **Name** to a name of your choice, such as `Zulip`. Under
   **New Conditions**, add the conditions for triggering a notification.
   Check the **Enabled** option, and click **Operations**.

1. Set **Default Subject** to `{TRIGGER.STATUS}-{TRIGGER.SEVERITY}-{TRIGGER.NAME}`.
   Set **Default Message** to the following:

    ```
    {
        "hostname": "{HOST.NAME}",
        "severity": "{TRIGGER.SEVERITY}",
        "status": "{TRIGGER.STATUS}",
        "item": "{ITEM.NAME1} is {ITEM.VALUE1}",
        "trigger": "{TRIGGER.NAME}",
        "link": "https://zabbix.example.com/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}"
    }
    ```

    Replace the `https://zabbix.example.com/` part of the **link** attribute with
    the URL for your own Zabbix server. Click **New**, and under **Send to Users**,
    click **Add**. Select the user you selected in step 6, and click **Select**.
    Under **Send only to**, select **Zulip**, and click **Add**.

{!congrats.md!}

![](/static/images/integrations/zabbix/001.png)
