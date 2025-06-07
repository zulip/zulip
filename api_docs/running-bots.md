# Interactive bots

Zulip's API has a powerful framework for interactive bots that react
to messages in Zulip.

## Running a bot

This guide will show you how to run an existing Zulip bot
found in [zulip_bots/bots](
https://github.com/zulip/python-zulip-api/tree/main/zulip_bots/zulip_bots/bots).

You'll need:

* An account in a Zulip organization
  (e.g., [the Zulip development community](https://zulip.com/development-community/),
  `{{ display_host }}`, or a Zulip organization on your own
  [development](https://zulip.readthedocs.io/en/latest/development/overview.html) or
  [production](https://zulip.readthedocs.io/en/latest/production/install.html) server).
* A computer where you're running the bot from.

**Note: Please be considerate when testing experimental bots on public servers such as chat.zulip.org.**

{start_tabs}

1. [Create a bot](/help/add-a-bot-or-integration), making sure to select
   **Generic bot** as the **Bot type**.

1. [Download the bot's `zuliprc` file](/api/configuring-python-bindings#download-a-zuliprc-file).

1. Use the following command to install the
   [`zulip_bots` Python package](https://pypi.org/project/zulip-bots/):

        pip3 install zulip_bots

1. Use the following command to start the bot process *(replacing
   `~/path/to/zuliprc` with the path to the `zuliprc` file you downloaded above)*:

        zulip-run-bot <bot-name> --config-file ~/path/to/zuliprc

1. Check the output of the command above to make sure your bot is running.
   It should include the following line:

        INFO:root:starting message handling...

1. Test your setup by [starting a new direct message](/help/starting-a-new-direct-message)
   with the bot or [mentioning](/help/mention-a-user-or-group) the bot on a channel.

!!! tip ""

    To use the latest development version of the `zulip_bots` package, follow
    [these steps](writing-bots#installing-a-development-version-of-the-zulip-bots-package).

{end_tabs}

You can now play around with the bot and get it configured the way you
like.  Eventually, you'll probably want to run it in a production
environment where it'll stay up, by [deploying](/api/deploying-bots) it on a
server using the Zulip Botserver.

## Common problems

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that your bot script is located in `zulip_bots/bots/<my-bot>/`
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot.

## Related articles

* [Non-webhook integrations](/api/non-webhook-integrations)
* [Deploying bots](/api/deploying-bots)
* [Writing bots](/api/writing-bots)
