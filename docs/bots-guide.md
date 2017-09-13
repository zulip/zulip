# Zulip bot system

Zulip's features can be extended by the means of bots and integrations.

* **Integrations** are used to connect Zulip with different chat, scheduling and workflow software.
  If this is what you are looking for, please check out the [integrations guide](
  http://zulip.readthedocs.io/en/latest/integration-guide.html?highlight=integrations).
* **Bots**, as a more general concept, intercept and react to messages.
  If this is what you are looking for, read on!

The purpose of this documentation is to provide you with information about Zulip's
bot system.

On this page you'll find:

* A step-by-step [tutorial](#how-to-run-a-bot) on how to run a bot.
* A step-by-step [tutorial](#how-to-develop-a-bot) on how to develop a bot.
* A [documentation](#bot-api) of the bot API.
* Common [problems](#common-problems) when developing/running bots and their solutions.

Contributions to this guide are very welcome, so if you run into any
issues following these instructions or come up with any tips or tools
that help with writing bots, please visit
[#integrations](https://chat.zulip.org/#narrow/stream/integrations) on the
[Zulip development community server](https://chat.zulip.org), open an
issue, or submit a pull request to share your ideas!

## The bots system

Zulip's bot system resides in the [python-zulip-api](
https://github.com/zulip/python-zulip-api) repository.

The structure of the bots ecosystem looks like the following:

```
zulip_bots
└───zulip_bots
    ├───bots
    │   ├───bot1
    │   └───bot2
    │       │
    │       ├───bot2.py
    │       ├───bot2.conf
    │       ├───doc.md
    │       ├───test_bot2.py
    │       ├───assets
    │       │   │
    │       │   └───pic.png
    │       ├───fixtures
    │       │   │
    │       │   └───test1.json
    │       └───libraries
    │           │
    │           └───lib1.py
    ├─── lib.py
    ├─── test_lib.py
    ├─── run.py
    └─── provision.py
```

Each subdirectory in `bots` contains a bot. When developing bots, try to use the structure outlined
above as an orientation.

## Installing the `zulip_bots` package

The `zulip_bots` package comes with all you need to run a bot.

### Installing a stable version

Run `pip install zulip_bots`.

### Installing a development version

1. `git clone https://github.com/zulip/python-zulip-api.git` - clone the [python-zulip-api](
  https://github.com/zulip/python-zulip-api) repository.

2. `cd python-zulip-api` - navigate into your cloned repository.

3. `./tools/provision` - install all requirements in a Python virtualenv.

4. Run the `source <activation/path>` command printed in the previous step to activate the virtualenv.

5. *Finished*. You should now see the name of your venv preceding your prompt, e.g. `(ZULIP-~1)`.

*Hint: `./tools/provision` installs `zulip`, `zulip_bots`, and `zulip_botserver` in developer
 mode. This enables you to make changes to the code after the packages are installed.*

## How to run a bot

This guide will show you how to run a bot on a running Zulip
server.  It assumes you want to use one of the existing `zulip_bots/bots`
bots in your Zulip organization.  If you want to write a new one, you
just need to write the `<my-bot>.py` script and put it into `zulip_bots/bots/<my-bot>` directory.

*Looking for an easy way to test a bot's output? Check out [this](
 #testing-a-bot-s-output) section.*

You need:

* An account in an organization on a Zulip server
  (e.g. [chat.zulip.org](https://chat.zulip.org) or
  yourSubdomain.zulipchat.com, or your own development server).
  Within that Zulip organization, users will be able to interact with
  your bot.
* A computer where you're running the bot from.

**Note: Please be considerate when testing experimental bots on
  public servers such as chat.zulip.org.**

1. [Install all requirements](#installing-the-zulip-bots-package).

2. Register a new bot user on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Settings (<i class="fa fa-cog"></i>)* -> *Your bots* -> *Add a new bot*.
      Select *Generic bot* for bot type, fill out the form and click on *Create bot*.
    * A new bot user should appear in the *Active bots* panel.

3. Download the bot's `.zuliprc` configuration file to your computer.

    * In the *Active bots* panel, click on the little green download icon
      to download its configuration file *.zuliprc* (the structure of this file is
      explained [here](#configuration-file)).
    * Copy the file to a destination of your choice, e.g. to `~/.zuliprc`.

4. Subscribe the bot to the streams that the bot needs to interact with.

    * To subscribe your bot to streams, navigate to *Manage
      Streams*. Select a stream and add your bot by its email address
      (the address you assigned in step 2).
    * Now, the bot can do its job on the streams you subscribed it to.
    * (In future versions of the API, this step may not be required).

5. Run the bot.

    * Run
      ```
      zulip-run-bot <bot-name> --config-file ~/.zuliprc
      ```
      (using the path to the `.zuliprc` file from step 3).
    * Check the output of the command. It should start with the text
      the `usage` function returns, followed by logging output similar
      to this:

      ```
      INFO:root:starting message handling...
      INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
      ```

    * Congrats! Now, your bot should be ready to test on the streams you've subscribed it to.

### Testing the helloworld bot

* The `helloworld` bot is a simple bot that responds with a 'beep boop'
  when queried. It can be used as a template to build more complex
  bots.
* Go to a stream your bot is subscribed to. Talk to the bot by
  typing `@<your bot name>` followed by some commands. If the bot is
  the `helloworld` bot, you should expect the bot to respond with
  "beep boop".

### Testing a bot's output

If you just want to see how a bot reacts to a message, but don't want to set it up on a server,
we have a little tool to help you out: `zulip-bot-output`

* [Install all requirements](#installing-the-zulip-bots-package).

* Run `zulip-bot-output <bot-name> --message "<your-message>"` to test one of the bots in
  [`zulip_bots/bots`](https://github.com/zulip/python-zulip-api/tree/master/zulip_bots/zulip_bots/bots)

  * Example: `zulip-bot-output converter --message "12 meter yard"`

    Response: `12.0 meter = 13.12336 yard`

* Run `zulip-bot-output <path/to/bot.py> --message "<your-message>"` to specify the bot's path yourself.

  * Example: `zulip-bot-output zulip_bots/zulip_bots/bots/converter/converter.py --message "12 meter yard"`

    Response: `12.0 meter = 13.12336 yard`

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
    webhook bots. It's structure is very similar to that of .zuliprc.

3.  Run the Zulip Botserver by passing the `flaskbotrc` to it. The
    command format is:

    ```
    zulip-bot-server  --config-file <path_to_flaskbotrc> --hostname <address> --port <port>
    ```

    If omitted, `hostname` defaults to `127.0.0.1` and `port` to `5002`.

4.  Now set up the outgoing webhook service which will interact with
    the server: Create an **Outgoing webhook** bot with its base url
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

    *Please note that in order to @-mention trigger a bot on a stream,
    the bot **and** the outgoing webhook bot need to be subscribed to
    it.*

### Running Zulip Botserver with `supervisord`

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
      * Download the [sample config file](
        https://raw.githubusercontent.com/zulip/python-zulip-api/master/zulip_botserver/zulip-botserver-supervisord.conf)
        and store it in `/etc/supervisor/conf.d/zulip-botserver.conf`.
      * Copy the following section into your existing supervisord config file.
        ```
        [program:zulip-bot-server]
        command=zulip-bot-server --config-file=<path/to/your/flaskbotrc> --hostname <address> --port <port>
        startsecs=3
        stdout_logfile=/var/log/zulip-botserver.log ; all output of your botserver will be logged here
        redirect_stderr=true
        ```
    * Edit the `<>` sections according to your preferences.

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

## How to develop a bot

The tutorial below explains the structure of a bot `<my-bot>.py`,
which is the only file you need to create for a new bot. You
can use this as boilerplate code for developing your own bot.

Every bot is built upon this structure:

```
class MyBotHandler(object):
    '''
    A docstring documenting this bot.
    '''

    def usage(self):
        return '''Your description of the bot'''

    def handle_message(self, message, bot_handler, state_handler):
        # add your code here

handler_class = MyBotHandler
```

* The class name (in this case *MyBotHandler*) can be defined by you
  and should match the name of your bot. To register your bot's class,
  adjust the last line `handler_class = MyBotHandler` to match your
  class name.

* Every bot needs to implement the functions
    * `usage(self)`
    * `handle_message(self, message, bot_handler)`

* These functions are documented in the [next section](#bot-api).

## Bot API

This section documents functions available to the bot and the structure of the bot's config file.

With this API, you *can*

* intercept, view, and process messages sent by users on Zulip.
* send out new messages as replies to the processed messages.

With this API, you *cannot*

* modify an intercepted message (you have to send a new message).
* send messages on behalf of or impersonate other users.
* intercept private messages (except for PMs with the bot as an
explicit recipient).

### usage

*usage(self)*

is called to retrieve information about the bot.

##### Arguments

* self - the instance the method is called on.

#### Return values

* A string describing the bot's functionality

#### Example implementation

```
def usage(self):
    return '''
        This plugin will allow users to flag messages
        as being follow-up items.  Users should preface
        messages with "@followup".
        Before running this, make sure to create a stream
        called "followup" that your API user can send to.
        '''
```

### handle_message

*handle_message(self, message, bot_handler)*

handles user message.

#### Arguments

* self - the instance the method is called on.

* message - a dictionary describing a Zulip message

* bot_handler - used to interact with the server, e.g. to send a message

* state_handler - used to save states/information of the bot **beta**
    * use `state_handler.set_state(state)` to set a state (any object)
    * use `state_handler.get_state()` to retrieve the state set; returns a `NoneType` object if no state is set

#### Return values

None.

#### Example implementation

 ```
  def handle_message(self, message, bot_handler, state_handler):
     original_content = message['content']
     original_sender = message['sender_email']
     new_content = original_content.replace('@followup',
                                            'from %s:' % (original_sender,))

     bot_handler.send_message(dict(
         type='stream',
         to='followup',
         subject=message['sender_email'],
         content=new_content,
     ))
 ```
### bot_handler.send_message

*bot_handler.send_message(message)*

will send a message as the bot user.  Generally, this is less
convenient than *send_reply*, but it offers additional flexibility
about where the message is sent to.

### Arguments

* message - a dictionary describing the message to be sent by the bot

### Example implementation

```
bot_handler.send_message(dict(
    type='stream', # can be 'stream' or 'private'
    to=stream_name, # either the stream name or user's email
    subject=subject, # message subject
    content=message, # content of the sent message
))
```

### bot_handler.send_reply

*bot_handler.send_reply(message, response)*

will reply to the triggering message to the same place the original
message was sent to, with the content of the reply being *response*.

### Arguments

* message - Dictionary containing information on message to respond to
 (provided by `handle_message`).
* response - Response message from the bot (string).

### bot_handler.update_message

*bot_handler.update_message(message)*

will edit the content of a previously sent message.

### Arguments

* message - dictionary defining what message to edit and the new content

### Example

From `zulip_bots/bots/incrementor/incrementor.py`:

```
bot_handler.update_message(dict(
    message_id=self.message_id, # id of message to be updated
    content=str(self.number), # string with which to update message with
))
```

### Configuration file

 ```
 [api]
 key=<api-key>
 email=<email>
 site=<dev-url>
 ```

* key - the API key you created for the bot; this is how Zulip knows
  the request is from an authorized user.

* email - the email address of the bot, e.g. `some-bot@zulip.com`

* site - your development environment URL; if you are working on a
  development environment hosted on your computer, use
  `localhost:9991`

## Common problems

* I modified my bot's code, yet the changes don't seem to have an effect.
    * Ensure that you restarted the `run.py` script.

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that you bot script is located in zulip_bots/bots/<my-bot>/
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot.

* My bot works only on some streams.
    * Subscribe your bot to other streams, as described [here](#how-to-run-a-bot).

## Future direction

The long-term plan for this bot system is to allow the same
`ExternalBotHandler` code to eventually be usable in several contexts:

* Run directly using the Zulip `call_on_each_message` API, which is
  how the implementation above works.  This is great for quick
  development with minimal setup.
* Run in a simple Python webserver server, processing messages
  received from Zulip's outgoing webhooks integration.
* For bots merged into the mainline Zulip codebase, enabled via a
  button in the Zulip web UI, with no code deployment effort required.
