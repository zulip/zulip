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

This guide will show you how to run a bot on a running Zulip
server.  It assumes you want to use one of the existing bots
found in [`zulip_bots/bots`](
https://github.com/zulip/python-zulip-api/tree/master/zulip_bots/zulip_bots/bots)
in your Zulip organization.

*Hint: Looking for an easy way to test a bot's output? Check out [this](
 writing-bots#testing-a-bots-output) guide.*

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

2. Register a new bot user on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Settings (<i class="fa fa-cog"></i>)* -> *Your bots* -> *Add a new bot*.
      Select *Generic bot* for bot type, fill out the form and click on *Create bot*.
    * A new bot user should appear in the *Active bots* panel.

3. Download the bot's `zuliprc` configuration file to your computer.

    * Go to *Settings* -> *Your bots*
    * In the *Active bots* panel, click on the little green download icon
      to download its configuration file *zuliprc* (the structure of this file is
      explained [here](writing-bots#configuration-file)).
    * The file will be downloaded to some place like `~/Downloads/zuliprc` (depends
      on your browser and OS).
    * Copy the file to a destination of your choice, e.g. to `~/zuliprc-my-bot`.

4. Run the bot.

    * Run
      ```
      zulip-run-bot <bot-name> --config-file ~/zuliprc-my-bot
      ```
      (using the path to the `zuliprc` file from step 3).
    * Check the output of the command. It should start with the text
      the `usage` function returns, followed by logging output similar
      to this:

            INFO:root:starting message handling...
            INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost

    * Congrats! Your bot is running.

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

1. Register new bot users on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Settings (<i class="fa fa-cog"></i>)* -> *Your bots* -> *Add a new bot*.
      Select *Outgoing webhook* for bot type, fill out the form and click on *Create bot*.
    * A new bot user should appear in the *Active bots* panel.

2.  Download the `flaskbotrc` from the `your-bots` settings page. It
    contains the configuration details for all the active outgoing
    webhook bots. It's structure is very similar to that of zuliprc.

3.  Run the Zulip Botserver by passing the `flaskbotrc` to it. The
    command format is:

    ```
    zulip-bot-server  --config-file <path_to_flaskbotrc> --hostname <address> --port <port>
    ```

    If omitted, `hostname` defaults to `127.0.0.1` and `port` to `5002`.

4.  Now set up the outgoing webhook service which will interact with
    the server: Create an **Outgoing webhook** bot with its Endpoint URL
    of the form:

    ```
    http://<hostname>:<port>/bots/<bot_name>
    ```

    `bot_name` refers to the name in the email address you specified
    for the bot. It can be obtained by removing `-bot@*.*` from the
    bot email: For example, the bot name of a bot with an email
    `followup-bot@zulip.com` is `followup`.

    In the development environment, an outgoing webhook bot and
    corresponding service already exist, with the email
    `outgoing-webhook@zulip.com`. This can be used for interacting
    with flask server bots.

5.  Congrats, everything is set up! Test your botserver like you would
    test a normal bot.

### Running Zulip Botserver with supervisord

[supervisord](http://supervisord.org/) is a popular tool for running
services in production.  It helps ensure the service starts on boot,
manages log files, restarts the service if it crashes, etc.  This
section documents how to run the Zulip Botserver using *supervisord*.

Running the Zulip Botserver with *supervisord* works almost like
running it manually.

0.  Install *supervisord* via your package manager; e.g. on Debian/Ubuntu:
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

2. Update *supervisord* to read the configuration file:
   ```
   supervisorctl reread
   supervisorctl update
   ```
   (or you can use `/etc/init.d/supervisord restart`, but this is less
   disruptive if you're using *supervisord* for other services as well).

3. Test if your setup is successful:
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
