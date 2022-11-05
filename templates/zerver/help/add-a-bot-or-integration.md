# Add a bot or integration

By default, anyone other than guests can add a bot to a Zulip organization.
A bot that sends content to or from another product is often called an
**integration**.

Organization administrators can also
[restrict bot creation](/help/restrict-bot-creation). Any bot that is added
is visible and available for anyone to use.

## Add a bot or integration

{start_tabs}

{tab|via-personal-settings}

{settings_tab|your-bots}

1. Click **Add a new bot**.

1. Fill out the fields, and click **Add**.

{tab|via-organization-settings}

{settings_tab|bot-list-admin}

1. Click **Add a new bot**.

1. Fill out the fields, and click **Add**.

{end_tabs}

!!! warn ""

    See [bots and integrations](/help/bots-and-integrations) for more information about
    the various fields.
    Nearly all third-party integrations should use **Incoming webhook**
    as the **bot type**.

Depending on the type of bot you're creating, you may need to download its
`.zuliprc` configuration file. For that, click the **download**
(<i class="fa fa-download"></i>) icon under the bot's name.

## Related articles

* [Bots and integrations](/help/bots-and-integrations)
* [Edit a bot](/help/edit-a-bot)
* [Deactivate or reactivate a bot](/help/deactivate-or-reactivate-a-bot)
* [Restrict bot creation](/help/restrict-bot-creation)
* [View all bots in your organization](/help/view-all-bots-in-your-organization)
