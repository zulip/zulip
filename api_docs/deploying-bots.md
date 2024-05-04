# Deploying bots in production

Usually, work on a bot starts on a laptop.  At some point, you'll want
to deploy your bot in a production environment, so that it'll stay up
regardless of what's happening with your laptop.  There are several
options for doing so:

* The simplest is running `zulip-run-bot` inside a `screen` session on
  a server.  This works, but if your server reboots, you'll need to
  manually restart it, so we don't recommend it.
* Using `supervisord` or a similar tool for managing a production
  process with `zulip-run-bot`.  This consumes a bit of resources
  (since you need a persistent process running), but otherwise works
  great.
* Using the Zulip Botserver, which is a simple Flask server for
  running a bot in production, and connecting that to Zulip's outgoing
  webhooks feature.  This can be deployed in environments like
  Heroku's free tier without running a persistent process.

## Zulip Botserver

The Zulip Botserver is for people who want to

* run bots in production.
* run multiple bots at once.

The Zulip Botserver is a Python (Flask) server that implements Zulip's
outgoing webhooks API.  You can of course write your own servers using
the outgoing webhooks API, but the Botserver is designed to make it
easy for a novice Python programmer to write a new bot and deploy it
in production.

### How Botserver works

Zulip Botserver starts a web server that listens to incoming messages
from your main Zulip server. The sequence of events in a successful
Botserver interaction are:

1. Your bot user is mentioned or receives a direct message:

    ```
    @**My Bot User** hello world
    ```

1. The Zulip server sends a POST request to the Botserver on `https://bot-server.example.com/`:

    ```
    {
      "message":{
        "content":"@**My Bot User** hello world",
      },
      "bot_email":"myuserbot-bot@example.com",
      "trigger":"mention",
      "token":"XXXX"
    }
    ```

    This URL is configured in the Zulip web-app in your Bot User's settings.

1. The Botserver searches for a bot to handle the message, and executes your
   bot's `handle_message` code.

Your bot's code should work just like it does with `zulip-run-bot`;
for example, you reply using
[bot_handler.send_reply](writing-bots#bot_handlersend_reply)).

### Installing the Zulip Botserver

Install the `zulip_botserver` package:

```
pip3 install zulip_botserver
```

### Running a bot using the Zulip Botserver

{start_tabs}

1. Construct the URL for your bot, which will be of the form:

    ```
    http://<hostname>:<port>
    ```

    where the `hostname` is the hostname you'll be running the bot
    server on, and `port` is the port for it (the recommended default
    is `5002`).

1. Register new bot users on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Personal settings (<i class="zulip-icon zulip-icon-gear"></i>)* -> *Bots* -> *Add a new bot*.
      Select *Outgoing webhook* for bot type, fill out the form (using
      the URL from above) and click on *Create bot*.
    * A new bot user should appear in the *Active bots* panel.

1. Download the `zuliprc` file for your bot from the *Active Bots*
   panel, using the download button.

1. Run the Botserver, where `helloworld` is the name of the bot you
   want to run:

    `zulip-botserver --config-file <path_to_zuliprc> --bot-name=helloworld`

    You can specify the port number and various other options; run
    `zulip-botserver --help` to see how to do this.

1.  Congrats, everything is set up! Test your Botserver like you would
    test a normal bot.

{end_tabs}

### Running multiple bots using the Zulip Botserver

The Zulip Botserver also supports running multiple bots from a single
Botserver process.  You can do this with the following procedure.

{start_tabs}

1. Download the `botserverrc` from the `your-bots` settings page, using
   the "Download config of all active outgoing webhook bots in Zulip
   Botserver format." option at the top.

1. Open the `botserverrc`. It should contain one or more sections that look like this:

    ```
    []
    email=foo-bot@hostname
    key=dOHHlyqgpt5g0tVuVl6NHxDLlc9eFRX4
    site=http://hostname
    token=aQVQmSd6j6IHphJ9m1jhgHdbnhl5ZcsY
    ```

    Each section contains the configuration for an outgoing webhook bot. For each
    bot, enter the name of the bot you want to run in the square brackets `[]`.
    For example, if we want `foo-bot@hostname` to run the `helloworld` bot, our
    new section would look like this:

    ```
    [helloworld]
    email=foo-bot@hostname
    key=dOHHlyqgpt5g0tVuVl6NHxDLlc9eFRX4
    site=http://hostname
    token=aQVQmSd6j6IHphJ9m1jhgHdbnhl5ZcsY
    ```

    To run an external bot, enter the path to the bot's python file in the square
    brackets `[]`. For example, if we want to run `~/Documents/my_new_bot.py`, our
    new section could look like this:

    ```
    [~/Documents/my_new_bot.py]
    email=foo-bot@hostname
    key=dOHHlyqgpt5g0tVuVl6NHxDLlc9eFRX4
    site=http://hostname
    ```

1.  Run the Zulip Botserver by passing the `botserverrc` to it. The
    command format is:

     ```
     zulip-botserver  --config-file <path_to_botserverrc>
     ```

     If omitted, `hostname` defaults to `127.0.0.1` and `port` to `5002`.

{end_tabs}

### Running Zulip Botserver with supervisord

[supervisord](http://supervisord.org/) is a popular tool for running
services in production.  It helps ensure the service starts on boot,
manages log files, restarts the service if it crashes, etc.  This
section documents how to run the Zulip Botserver using *supervisord*.

Running the Zulip Botserver with *supervisord* works almost like
running it manually.

{start_tabs}

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

            [program:zulip-botserver]
            command=zulip-botserver --config-file=<path/to/your/botserverrc>
            --hostname <address> --port <port>
            startsecs=3
            stdout_logfile=/var/log/zulip-botserver.log ; all output of your Botserver will be logged here
            redirect_stderr=true

    * Edit the `<>` sections according to your preferences.

[supervisord-config-file]: https://raw.githubusercontent.com/zulip/python-zulip-api/main/zulip_botserver/zulip-botserver-supervisord.conf

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
    > zulip-botserver                 RUNNING   pid 28154, uptime 0:00:27

    The standard output of the Botserver will be logged to the path in
    your *supervisord* configuration.

{end_tabs}

If you are hosting the Botserver yourself (as opposed to using a
hosting service that provides SSL), we recommend securing your
Botserver with SSL using an `nginx` or `Apache` reverse proxy and
[Certbot](https://certbot.eff.org/).

### Troubleshooting

- Make sure the API key you're using is for an [outgoing webhook
  bot](/api/outgoing-webhooks) and you've
  correctly configured the URL for your Botserver.

- Your Botserver needs to be accessible from your Zulip server over
  HTTP(S).  Make sure any firewall allows the connection.  We
  recommend using [zulip-run-bot](running-bots) instead for
  development/testing on a laptop or other non-server system.
  If your Zulip server is self-hosted, you can test by running `curl
  http://zulipbotserver.example.com:5002` from your Zulip server;
  the output should be:

    ```
    $ curl http://zulipbotserver.example.com:5002/
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <title>405 Method Not Allowed</title>
    <h1>Method Not Allowed</h1>
    <p>The method is not allowed for the requested URL.</p>
    ```

## Related articles

* [Non-webhook integrations](/api/non-webhook-integrations)
* [Running bots](/api/running-bots)
* [Writing bots](/api/writing-bots)
