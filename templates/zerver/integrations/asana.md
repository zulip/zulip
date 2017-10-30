Get Zulip notifications for your Asana projects via Zapier!

{!create-stream.md!}

Next, on your {{ settings_html|safe }}, create a bot for Asana.
Construct the URL for the Asana bot using the bot API key and
stream name, like so:

`{{ api_url }}/v1/external/zapier?api_key=abcdefgh&stream=asana`

Start by setting up a [Zapier](https://zapier.com/) account.

Next, create a ZAP, picking Asana as the app you'd like
to receive notifications from as the **Trigger (Step 1)**:

![](/static/images/integrations/asana/001.png)

Next, select the Asana event that you'd like to receive notifications
for (**Choose Trigger**), such as when you add a new **Task** in
an Asana project:

![](/static/images/integrations/asana/002.png)

Next, click on **Connect a New Account** and follow the steps
to connect your Asana account to the Zap:

![](/static/images/integrations/asana/003.png)

Select the Asana project you'd like to receive notifications for:

![](/static/images/integrations/asana/004.png)

In **Action (Step 2)**, select **Webhooks by Zapier** as the app:

![](/static/images/integrations/asana/005.png)

and `POST` as the action:

![](/static/images/integrations/asana/006.png)

Configure **Set up Webhooks by Zapier POST** as follows:

* `URL` is the URL we created above
* `Payload Type` set to `JSON`

Finally, configure **Data**. You have to add 2 fields:

* `subject` is the field corresponding to the subject of the message
* `content` is the field corresponding to the content of the message

You can format the content of the `content` and `subject` fields
in a number of ways as per your requirements.

Here's an example configuration:

![](/static/images/integrations/asana/007.png)

{!congrats.md!}

![](/static/images/integrations/asana/008.png)

You can repeat the above process and create Zaps for different projects
and/or different kinds of Asana events that you'd like to be notified
about in Zulip.
