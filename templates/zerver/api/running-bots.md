# Interactive bots

Zulip's API has a powerful framework for interactive bots that react
to messages in Zulip.

## Running a bot

This guide will show you how to run an existing Zulip bot
found in [zulip_bots/bots](
https://github.com/zulip/python-zulip-api/tree/master/zulip_bots/zulip_bots/bots).

You'll need:

* An account in a Zulip organization
  (e.g. [chat.zulip.org](https://chat.zulip.org),
  `<yourSubdomain>.zulipchat.com`, or a Zulip organization on your own
  [development](https://zulip.readthedocs.io/en/latest/development/overview.html) or
  [production](https://zulip.readthedocs.io/en/latest/production/install.html) server).
* A computer where you're running the bot from.

**Note: Please be considerate when testing experimental bots on public servers such as chat.zulip.org.**

1. Go to your Zulip account and
   [add a bot](/help/add-a-bot-or-integration). Use **Generic bot** as the bot type.

1. Download the bot's `zuliprc` configuration file to your computer.

1. Download the `zulip_bots` Python package to your computer using `pip install zulip_bots`.

     *Note: Click
     [here](
     writing-bots#installing-a-development-version-of-the-zulip-bots-package)
     to install the latest development version of the package.*

1. Start the bot process on your computer.

    * Run
      ```
      zulip-run-bot <bot-name> --config-file ~/path/to/zuliprc
      ```

      (replacing `~/path/to/zuliprc` with the path to the `zuliprc` file you downloaded above).

    * Check the output of the command. It should include the following line:

            INFO:root:starting message handling...

        Congrats! Your bot is running.

1. To talk with the bot, at-mention its name, like `@**bot-name**`.

You can now play around with the bot and get it configured the way you
like.  Eventually, you'll probably want to run it in a production
environment where it'll stay up, by [deploying](/api/deploying-bots) it on a server using the
Zulip Botserver.

## Common problems

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that your bot script is located in `zulip_bots/bots/<my-bot>/`
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot.
