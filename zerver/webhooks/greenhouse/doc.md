Receive Greenhouse notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. On your Greenhouse **Dashboard**, click on the
   **gear** (<i class="fa fa-cog"></i>) icon in the upper right
   corner. Click on **Dev Center**, and click **Web Hooks**.
   Click on **Web Hooks** one more time.

1. Set **Name this web hook** to a name of your choice, such as
   `Zulip`. Set **When** to the event you'd like to be notified
   about. Set **Endpoint URL** to the URL constructed above.

1. Greenhouse requires you to provide a **Secret key**, but Zulip
   doesn't expect any particular value. Set **Secret key** to any
   random value, and click **Create Web hook**.

{!congrats.md!}

![](/static/images/integrations/greenhouse/000.png)
