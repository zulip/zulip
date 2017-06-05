{!create-stream.md!}

However, the integration will use the default stream `commits`
if no stream is supplied in the hook; you still need to
[create the stream](../help/create-a-stream) even if you are
using this default.

{!create-bot-construct-url.md!}

{!git-webhook-url-with-branches.md!}

Next, go to your repository page and click **Settings**:

![](/static/images/integrations/gogs/001.png)

On the **Settings** page, select the **Webhooks** link on the
left sidebar:

![](/static/images/integrations/gogs/002.png)

Click the **Add Webhook** button and then select the **Gogs**
option from the dropdown that appears.

![](/static/images/integrations/gogs/003.png)

Authorize yourself and configure your webhook.

In the **Payload URL** field, enter the URL created above.

Then, set **Content type** to **application/json**.

Next, select the events that you want to trigger Zulip
notifications. After you have selected all the desired events,
click the **Add Webhook** button.

![](/static/images/integrations/gogs/004.png)

{!congrats.md!}

![](/static/images/integrations/gogs/005.png)
