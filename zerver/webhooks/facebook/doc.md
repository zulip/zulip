{!create-stream.md!}

Next, on your {{ settings_html|safe }},
[create a bot](/help/add-a-bot-or-integration) for
{{ integration_display_name }}. Make sure that you select
**Incoming webhook** as the **Bot type**:

![](/static/images/help/bot_types.png)

The API key for an incoming webhook bot cannot be used to read messages out
of Zulip. Thus, using an incoming webhook bot lowers the security risk of
exposing the bot's API key to a third-party service.

Construct the URL for the {{ integration_display_name }}
bot using the bot's API key and the desired stream name:

`{{ api_url }}{{ integration_url }}?api_key=abcdefgh&stream={{ recommended_stream_name }}&token=sampletoken`

Modify the parameters of the URL above, where `api_key` is the API key
of your Zulip bot, and `stream` is the stream name you want the
notifications sent to.

`token` is an arbitrary string of your choosing that can be used to confirm to your
 server that the request is valid. This string will be included in Facebook's
 incoming payloads each time they send your server a verification request.

{!append-stream-name.md!}

### Configuring the webhook

Sign In to the following URL: <https://developers.facebook.com/apps/>

Next, click on **+ Add a New App** button.

![](/static/images/integrations/facebook/001.png)

Then, fill in the following form to create a new Facebook app:

![](/static/images/integrations/facebook/002.png)

Next, under **Webhooks**, click on **Set up**:

![](/static/images/integrations/facebook/003.png)

Choose a category for the webhook:

![](/static/images/integrations/facebook/004.png)

This guide explains how to subscribe to a "feed" in the **User** category.

Select the **User** category, and click on **Subscribe to this topic**.
Fill in the **Edit User Subscription** form as follows:

1. **Callback URL**: enter the webhook URL created above.
2. **Verify Token**: enter the token you chose above. For instance, in this example you may enter **sampletoken**
3. Activate the **Include Values** option.
4. Click on **Verify and Save**.

The resulting form would look like:

![](/static/images/integrations/facebook/005.png)

Finally, click **Subscribe** and **Test** in the **feed** row, like so:

![](/static/images/integrations/facebook/006.png)

Click on **Send to My Server** and a test message will be sent to your Zulip server.

![](/static/images/integrations/facebook/007.png)

{!congrats.md!}

![](/static/images/integrations/facebook/008.png)

**This integration is not created by, affiliated with, or supported by Facebook, Inc.**
