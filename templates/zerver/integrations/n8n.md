# Zulip n8n integration

n8n supports integrations with
[hundreds of popular products](https://n8n.io/integrations/). Use the Zulip
action node in n8n workflows to send notifications, manage messages, users,
and channels.

{start_tabs}

1. {!create-a-generic-bot.md!}

1. [Download the `zuliprc` file](/help/manage-a-bot#download-zuliprc-configuration-file)
   for the bot you created above.

1. Open your n8n workflow, and add the **Zulip** action node.

1. Click **Set up credential**, and enter the **URL** for your Zulip
   organization, the bot's **email address**, and **API key** from the
   `zuliprc` file you downloaded above. Click **Save**, and close the
   credentials modal.

1. Under **Resource**, select the Zulip resource type (message, user, or
   channel). Under **Operation**, select the action to perform on the
   selected resource, and fill out the corresponding parameters.

1. Click **Execute step** or **Execute workflow** to test it.

{end_tabs}

You're done! You should now be able to interact with your Zulip organization
via n8n workflows.

### Related documentation

- [n8n Zulip integration][n8n-zulip]
- [Zulip action node][zulip-node]

[n8n-zulip]: https://n8n.io/integrations/zulip/
[zulip-node]: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.zulip/
