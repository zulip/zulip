See your Splunk Search alerts in Zulip!

{!create-stream.md!}

{!create-bot-construct-url.md!}

{!append-topic.md!}

Next, in the Splunk search app, execute the search you'd like to be
alerted on and then save it as an alert:

![](/static/images/integrations/splunk/splunk_save_as_alert.png)

Name and configure your search in the **Settings** and **Trigger Conditions**
sections of the **Save As Alert** dialog box.

In the **Trigger Actions** section, click **Add Actions** and select
**Webhook** to add a webhook action. Put the Zulip Splunk webhook URL
we created earlier.

If you do not specify a stream in the URL, your messages will use
the default stream `splunk`. If you do not specify a topic,
the name of the search is used (truncated to fit if needed.)

When you are done, it should look like this:

![](/static/images/integrations/splunk/splunk_configure_url.png)

Click **Save** to save the alert. You can create as many searches with
alert actions as you like, with whatever stream and topic you choose.
Update your webhook URL as appropriate for each one, and make sure the
stream exists.

{!congrats.md!}

![](/static/images/integrations/splunk/splunk_message.png)
