Zulip supports both SVN and Git notifications from Beanstalk.

1. {!create-stream.md!}

1. {!create-a-bot-indented.md!}

   {!webhook-url-with-bot-email-indented.md!}
   {!git-append-branches.md!}

1. On your repository's webpage, click on the **Settings**
   tab. Click on the **Integrations** tab, scroll down and click on
   **Modular Webhooks**. Click on **Add a webhook**.

1. Set **Name** to a name of your choice, such as `Zulip`.
   Set **URL** to the URL constructed above. Under
   **Select webhook triggers**, check the events that you would
   like to receive notifications for, and click **Activate**.

{!congrats.md!}

![](/static/images/integrations/beanstalk/001.png)
