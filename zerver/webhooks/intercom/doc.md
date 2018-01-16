{!create-stream.md!}

{!create-bot-construct-url.md!}

Intercom will use the `intercom` stream by default if no stream is given
in the URL. Make sure the selected stream exists in Zulip.

**Follow these steps:**

1. Go to the Integrations Page of your Intercom Console.

2. Find and select the `Zapier` integration option.

3. Create an account on `Zapier` if you haven't
already. Click on **Explore Intercom on Zapier!**.

4. Select **Make A ZAP**. Choose `Intercom `in the apps section and
`Webhooks` in the built-in apps section.

5. Authenticate with your Intercom account to connect it with
`Zapier`.

6. Select the actions which will trigger the webhook.

7. Select **POST** on the page that says **Webhooks by Zapier Action**, and
click **Continue**.

8. In the **URL** field, enter the URL constructed above. Select `JSON`
for **Payload Type** and click **Continue**:

{!congrats.md!}

![](/static/images/integrations/intercom/001.png)
