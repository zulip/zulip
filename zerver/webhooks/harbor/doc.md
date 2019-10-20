Get Zulip notifications for your [Harbor](https://goharbor.io/) projects!

Harbor's webhooks feature is available in version 1.9 and later.

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to your Harbor **Projects** page. Open a project and click on the **Webhooks** tab.

1. Set **Endpoint URL** to the URL constructed above and click on **Continue**. We
   currently support the following events:
    * pushImage
    * scanningCompleted

{!congrats.md!}

![](/static/images/integrations/harbor/001.png)
