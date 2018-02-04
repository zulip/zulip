*If you are running JIRA version 5.2 or greater, or if you are
using the hosted JIRA provided by Atlassian, you can use the built-in
web-hook support to connect to Zulip — read on. For older,
self-hosted JIRA installs, you can use our [JIRA Plugin](./jira-plugin).*

{!create-stream.md!}

{!create-bot-construct-url.md!}

Next, in your JIRA administration control panel, go to the **Webhooks**
page. If you are using the OnDemand hosted JIRA, follow the instructions
[on the Atlassian wiki][1] for locating the Webhook UI.

[1]: https://developer.atlassian.com/jiradev/jira-apis/webhooks#Webhooks-jiraadmin

Give your new webhook a name, and for the URL provide the URL we
created above.

{!congrats.md!}

![](/static/images/integrations/jira/001.png)
