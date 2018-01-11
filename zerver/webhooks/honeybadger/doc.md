{!create-stream.md!}

{!create-bot-construct-url.md!}

Honeybadger will use the `honeybadger` stream by default if no stream is given
in the URL. Make sure the selected stream exists in Zulip.

**Follow these steps:**

1. Go to the `Alerts & Integrations` page in the project settings page of your Honeybadger
console.

2. Find and select the `WebHook` integration option.
![](/static/images/integrations/honeybadger/002.png)

3. Enter the URL constructed above into the URL field and configure
the triggers for the webhook.
![](/static/images/integrations/honeybadger/003.png)

4. Test the webhook by clicking on the `Test This Integration` button at the bottom of
the page.

5. Click `Save changes` to create the webhook.

{!congrats.md!}

![](/static/images/integrations/honeybadger/001.png)
