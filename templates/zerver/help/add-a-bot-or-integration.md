# Add a bot

By default, anyone other than guests can add a bot to a Zulip organization.
A bot that sends content to or from another product is often called an
**integration**.

Organization administrators can also
[restrict bot creation](/help/restrict-bot-creation). Any bot that is added
is visible and available for anyone to use.

## Add a bot

{settings_tab|your-bots}

2. Click **Add a new bot**.

3. Fill out the fields, and click **Create bot**.

!!! tip ""
    Our [guide to bots](/help/bots-and-integrations) has more information about
    the various fields.
    Nearly all third-party integrations should use **Incoming webhook**
    as the **bot type**.

Depending on the type of bot you're creating, you may need to download its
`.zuliprc` configuration file. For that, click the **download**
(<i class="fa fa-download"></i>) icon under the bot's name.
