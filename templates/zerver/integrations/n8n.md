# Zulip n8n integration

Use n8n to interact with your Zulip organization
and integrate it with other services in your workflows.

{start_tabs}

1. {!create-a-generic-bot.md!}

1. [Download the `zuliprc` file](/help/manage-a-bot#download-zuliprc-configuration-file)
   for the bot you created above.

1. Open your n8n workflow and add a new **Zulip** node.

1. Configure the Zulip node credentials by entering the **URL** for
   your Zulip organization, the bot's **email address** and **API key**
   from the `zuliprc` file you downloaded above.

1. Under **Resource**, select the type of resource you are working with
   and under **Operation**, select the action you want to perform.

1. Fill out the corresponding parameters for your selected operation.

1. Execute the node or workflow.

{end_tabs}

You're done! You should now be able to interact with your Zulip
organization from n8n workflows.

### Related documentation

- [n8n Zulip integration][n8n-zulip]

[n8n-zulip]: https://n8n.io/integrations/n8n-nodes-base.zulip
