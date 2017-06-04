{!create-stream.md!}

The integration will use the default stream `gitlab` if no stream
is supplied in the URL; you still need to create the stream even
if you are using this default.

{!create-bot-construct-url.md!}

{!git-webhook-url-with-branches.md!}

Next, go to your repository page and click the gear icon. From there,
select **Webhooks**:

![](/static/images/integrations/gitlab/001.png)

In the URL field, enter a URL constructed like the one above.

Select the actions that you want to result in a Zulip notification
and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/gitlab/002.png)
