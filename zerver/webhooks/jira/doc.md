Get Zulip notifications for your JIRA projects!

These instructions apply to Atlassian Cloud's hosted JIRA, and JIRA Server version
5.2 or greater. For older installs, you'll need our [JIRA Plugin](./jira-plugin).

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to your JIRA **Site administration** page. Click **Jira** on the left.
   On the left sidebar, scroll down, and under **Advanced**, click **WebHooks**.
   Click **+ Create a WebHook**.

1. Set **Name** to a name of your choice, such as `Zulip`. Set **Status** to
   **Enabled**, and set **URL** to the URL constructed above. Select the events
   you'd like to be notified about, and click **Create**. We
   support the following events:
    * when an issue is created
    * when an issue is deleted
    * when an issue is updated

{!congrats.md!}

![](/static/images/integrations/jira/001.png)
