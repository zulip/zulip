Receive Zulip notifications for your Taiga projects!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    Make sure to specify the topic in the URL above. Otherwise, the
    default topic `General` will be used.

1. Go to your **Projects Dashboard** on Taiga, and select the project you'd like to
   receive notifications for. Go to **Admin**, and click on  **Integrations**.
   Click on **Add a new webhook**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set **URL** to the
   URL constructed above, and set **Secret key** to the API key of the bot created
   above. Save the form.

{!congrats.md!}

![](/static/images/integrations/taiga/001.png)
