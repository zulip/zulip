See build and deploy statuses on Semaphore right in Zulip with the
Zulip Semaphore plugin!

{!create-stream.md!}

Next, on your {{ settings_html|safe }}, create a Semaphore bot.

Then, log into your account on
[semaphoreci.com](http://semaphoreci.com).

Visit the **Project Settings** page for the project for which
you'd like to generate Zulip notifications. Click the
**Notifications** tab in the left sidebar, click on **Webhooks**
in the resulting menu, and then click on **+ Add Webhook**.

![](/static/images/integrations/semaphore/001.png)

You should now see a form that looks like this:

![](/static/images/integrations/semaphore/002.png)

{!webhook-url-with-bot-email.md!}

{!append-stream-name.md!}

{!congrats.md!}

![](/static/images/integrations/semaphore/003.png)
