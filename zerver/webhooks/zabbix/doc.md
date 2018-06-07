Receive Zabbix notifications in Zulip!

1.  {!create-stream.md!}

2.  {!create-bot-construct-url-indented.md!}

3.  Create a script called `zulip.sh` in your `alertscripts` folder on your **Zabbix Server** containing
    the below code. You can also find the file [here]("https://github.com/adambirds/zabbix-to-zulip-script").
    The **alertscripts** folder is usually `/usr/lib/zabbix/alertscripts`.
    Yours may be different depending on your environment. Make sure the script is executable by your
    **Zabbix** environment.

        #!/bin/bash

        webhook_url="$1"

        # Build our JSON payload and send it as a POST request to the Zulip incoming web-hook URL
        payload="$3"
        echo $payload > /tmp/payload.txt
        /usr/bin/curl -m 5 --data "$payload" "${webhook_url}"

4.  Go to Zabbix Web Interface. Click **Administration** and then **Media Types**. Click **Create Media Type**.

    Enter `Zulip` as the **name** of the media type. Select `Script` as the **type**.

    Enter `zulip.sh` as the **Script name**. Enter `{ALERT.SENDTO}` as the **first** parameter.

    Enter `{ALERT.SUBJECT}` as the **second** parameter. Enter `{ALERT.MESSAGE}` as the **third** parameter.

    Tick **Enabled**. Click **Update**.

5.  Go to Zabbix Web Interface. Click **Administration** and then **Users**.
    Click the **alias** of the user in which you will use to set the notification.

    Once in the user's settings, click **Media**. Click **Add**. Set **Type** to `Zulip`.
    Set **Send To** as the URL you constructed in step 2.

    Tick the severity's for which you wish to notify for. Tick **Enabled**.

6.  Go to Zabbix Web Interface. Click **Configuration** and then **Actions**.
    Click **Create Action**.

    For the **Name**, you can enter as you wish, for example `Zulip Alerts`.

    Under the **New Conditions**, you can add whatever conditions you would like to filter your notifications.
    Tick **Enabled**. Click **Operations**.

    For the **Default Subject**, enter `{TRIGGER.STATUS}-{TRIGGER.SEVERITY}-{TRIGGER.NAME}`.

    For the **Default Message**, enter the below code, switching the hostname of your
    **Zabbix Web Interface** into the **link** item:

        {
        "hostname": "{HOST.NAME}",
        "severity": "{TRIGGER.SEVERITY}",
        "status": "{TRIGGER.STATUS}",
        "item": "{ITEM.NAME1} is {ITEM.VALUE1}",
        "trigger": "{TRIGGER.NAME}",
        "link": "https://zabbix.example.com/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}"
        }

    Click **New**. In the **Send to Users** section, click **Add**. Select the the user in which you
    set up the notification to go to in step 5. Click **Select**.

    Under the **Send only to** section, selct `Zulip`. Click the **Add** button within that section.

{!congrats.md!}

![](/static/images/integrations/zabbix/001.png)
