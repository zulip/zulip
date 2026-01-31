# Zulip Nextcloud integration

Send Nextcloud files in Zulip messages as uploaded files, public
shared links, or internal shared links.

{start_tabs}

1. {!create-a-generic-bot.md!}

1. Click on **Manage bot** (<i class="zulip-icon zulip-icon-user-cog"></i>)
   next to the bot’s name, scroll to the zuliprc configuration section
   and click **copy** (<i class="zulip-icon zulip-icon-copy"></i>) to
   copy the bot’s credentials.

1. Follow [the instructions in the Nextcloud App store][1] to set up this
   integration.

    * In Nextcloud, go to **User settings** > **Connected accounts**.
    * Enter the **Zulip server URL**, and paste the **bot email address**
      and **API key** you copied above.

{end_tabs}

You're done!You should be able to send NextCloud files to Zulip.

[1]: https://apps.nextcloud.com/apps/integration_zulip
