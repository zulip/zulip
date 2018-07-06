# Interactive bots

Zulip's API has a powerful framework for interactive bots that react
to messages in Zulip.  This page documents how to run a bot
implemented using that framework, both on your laptop for quick
testing as well in a production server environment.

On this page you'll find:

* A step-by-step [tutorial](#running-a-bot) on how to run a bot.
* Common [problems](#common-problems) when developing/running bots and their solutions.

## Installing the Zulip bots package

## Running a bot

This guide will show you how to run an **existing** Zulip bot
found in [`zulip_bots/bots`](
https://github.com/zulip/python-zulip-api/tree/master/zulip_bots/zulip_bots/bots).

You need:

* An account in an organization on a Zulip server
  (e.g. [chat.zulip.org](https://chat.zulip.org) or
  yourSubdomain.zulipchat.com, or your own development server).
  Within that Zulip organization, users will be able to interact with
  your bot.
* A computer where you're running the bot from.

**Note: Please be considerate when testing experimental bots on public servers such as chat.zulip.org.**

1. Run `pip install zulip_bots` to install the package.

     *Hint: Do you want to install the latest development version? Check
     out [this](
     writing-bots#installing-a-development-version-of-the-zulip-bots-package)
     guide.*

1. Register a new bot user on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Settings (<i class="fa fa-cog"></i>)* -> *Your bots* -> *Add a new bot*.
      Select *Generic bot* for bot type, fill out the form and click on *Create bot*.
    * A new bot user should appear in the *Active bots* panel.

1. Download the bot's `zuliprc` configuration file to your computer.

    * Go to *Settings* -> *Your bots*.
    * In the *Active bots* panel, click on the little green download icon
      to download its configuration file *zuliprc* (the structure of this file is
      explained [here](writing-bots#configuration-file)).
    * The file will be downloaded to some place like `~/Downloads/zuliprc` (depends
      on your browser and OS).
    * Copy the file to a destination of your choice, e.g. to `~/zuliprc-my-bot`.

1. Start the bot process.

    * Run
      ```
      zulip-run-bot <bot-name> --config-file ~/zuliprc-my-bot
      ```
      (using the path to the `zuliprc` file from step 3).
    * Check the output of the command. It should include the following line:

            INFO:root:starting message handling...

        Congrats! Your bot is running.

1. To talk with the bot, mention its name `@**bot-name**`.

You can now play around with the bot and get it configured the way you
like.  Eventually, you'll probably want to run it in a production
environment where it'll stay up, by deploying it on a server using the
Zulip Botserver.

## Common problems

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that your bot script is located in `zulip_bots/bots/<my-bot>/`
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot.
