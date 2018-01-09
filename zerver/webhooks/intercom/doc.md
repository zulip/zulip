{!create-stream.md!}

{!create-bot-construct-url.md!}

Intercom webhook will use the `test` stream by default if no stream is given
in the url. Make sure the selected stream exists in Zulip.

Next, go to the Integrations Console via your Intercom Console:

![](/static/images/integrations/intercom/008.png)

From there, find and select the Zapier Integration Option:

![](/static/images/integrations/intercom/002.png)

Follow the link. Create an account on Zapier if you haven't
already. Click on **Explore Intercom on Zapier!**:

![](/static/images/integrations/intercom/003.png)

Select **Make A ZAP**. Choose `Intercom `in the apps section and
`Webhooks` in the built in apps section:

![](/static/images/integrations/intercom/004.png)

Connect your Intercom Account to Zapier:

![](/static/images/integrations/intercom/005.png)

Select the actions which will trigger the webhook:

![](/static/images/integrations/intercom/006.png)

Select **POST** on the page that says **Webhooks by Zapier Action**,
and click **Continue**:

![](/static/images/integrations/intercom/007.png)

In the **URL** field, enter the URL constructed above. Select `JSON`
for **Payload Type** and click **Continue**:

{!congrats.md!}

![](/static/images/integrations/intercom/001.png)
