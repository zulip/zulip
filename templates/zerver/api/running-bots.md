# Interactive bots

Zulip's API has a powerful framework for interactive bots that react
to messages in Zulip.  This page documents how to run a bot
implemented using that framework, both on your laptop for quick
testing as well in a production server environment.

On this page you'll find:

* A step-by-step [tutorial](#running-a-bot) on how to run a bot.
* A [guide](#zulip-botserver) on running a Zulip botserver.
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

## Zulip Botserver

The Zulip Botserver is for people who want to

* run bots in production.
* run multiple bots at once.

The Zulip Botserver is a Python (Flask) server that implements Zulip's
Outgoing Webhooks API.  You can of course write your own servers using
the Outgoing Webhooks API, but the Botserver is designed to make it
easy for a novice Python programmer to write a new bot and deploy it
in production.

### Installing the Zulip Botserver

Install the `zulip_botserver` PyPI package using `pip`:
```
pip install zulip_botserver
```

### Running bots using the Zulip Botserver


1. Construct the URL for your bot, which will be of the form:

    ```
    http://<hostname>:<port>/bots/<bot_name>
    ```

    where the `hostname` is the hostname you'll be running the bot
    server on, and `port` is the port for it (the recommended default
    is `5002`).  `bot_name` is the name of the Python module for the
    bot you'd like to run.

1. Register new bot users on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Settings (<i class="fa fa-cog"></i>)* -> *Your bots* -> *Add a new bot*.
      Select *Outgoing webhook* for bot type, fill out the form (using
      the URL from above) and click on *Create bot*.
    * A new bot user should appear in the *Active bots* panel.

1.  Download the `flaskbotrc` from the `your-bots` settings page. It
    contains the configuration details for all the active outgoing
    webhook bots. It's structure is very similar to that of zuliprc.

1.  Run the Zulip Botserver by passing the `flaskbotrc` to it. The
    command format is:

    ```
    zulip-bot-server  --config-file <path_to_flaskbotrc> --hostname <address> --port <port>
    ```

    If omitted, `hostname` defaults to `127.0.0.1` and `port` to `5002`.

1.  Congrats, everything is set up! Test your botserver like you would
    test a normal bot.

### Running Zulip Botserver with supervisord

[supervisord](http://supervisord.org/) is a popular tool for running
services in production.  It helps ensure the service starts on boot,
manages log files, restarts the service if it crashes, etc.  This
section documents how to run the Zulip Botserver using *supervisord*.

Running the Zulip Botserver with *supervisord* works almost like
running it manually.

1.  Install *supervisord* via your package manager; e.g. on Debian/Ubuntu:
    ```
    sudo apt-get install supervisor
    ```

1.  Configure *supervisord*.  *supervisord* stores its configuration in
    `/etc/supervisor/conf.d`.
    * Do **one** of the following:
      * Download the [sample config file][supervisord-config-file]
        and store it in `/etc/supervisor/conf.d/zulip-botserver.conf`.
      * Copy the following section into your existing supervisord config file.

            [program:zulip-bot-server]
            command=zulip-bot-server --config-file=<path/to/your/flaskbotrc>
            --hostname <address> --port <port>
            startsecs=3
            stdout_logfile=/var/log/zulip-botserver.log ; all output of your botserver will be logged here
            redirect_stderr=true

    * Edit the `<>` sections according to your preferences.

[supervisord-config-file]: https://raw.githubusercontent.com/zulip/python-zulip-api/master/zulip_botserver/zulip-botserver-supervisord.conf

1. Update *supervisord* to read the configuration file:
   ```
   supervisorctl reread
   supervisorctl update
   ```
   (or you can use `/etc/init.d/supervisord restart`, but this is less
   disruptive if you're using *supervisord* for other services as well).

1. Test if your setup is successful:
   ```
   supervisorctl status
   ```
   The output should include a line similar to this:
   > zulip-bot-server                 RUNNING   pid 28154, uptime 0:00:27

   The standard output of the bot server will be logged to the path in
   your *supervisord* configuration.

## Common problems

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that your bot script is located in zulip_bots/bots/<my-bot>/
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot.
