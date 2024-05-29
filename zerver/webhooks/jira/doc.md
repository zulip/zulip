Get Zulip notifications for your Jira projects!

These instructions apply to Atlassian Cloud's hosted Jira, and Jira Server version
5.2 or greater. For older installs, you'll need our [Jira plugin](./jira-plugin).

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Go to your Jira **Site administration** page. Click **Jira** on the left.
   On the left sidebar, scroll down, and under **Advanced**, click **WebHooks**.
   Click **+ Create a WebHook**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set **Status** to
   **Enabled**, and set **URL** to the URL constructed above. Select the events
   you'd like to be notified about, and click **Create**. We
   support the following **Issue** and **Comment** events:
    * when an issue is created
    * when an issue is deleted
    * when an issue is updated
    * when a comment is added
    * when a comment is updated
    * when a comment is deleted

{!congrats.md!}

![](/static/images/integrations/jira/001.png)
