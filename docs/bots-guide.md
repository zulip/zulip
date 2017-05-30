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
[#bots](https://chat.zulip.org/#narrow/stream/bots) on the
[Zulip development community server](https://chat.zulip.org), open an
issue, or submit a pull request to share your ideas!

# The bots system

Zulip's bot system resides in the `api` directory.

The structure of the bots ecosystem in the `api` directory looks like the following:

```
api
└───bots
    └───bot1
    └───bot2
        │
        └───readme.md
        └───bot2.py
        └───bot2.config
        └───libraries
        |   |
        |   └───lib1.py
        └───assets
           |
           └───pic.png
├── bots_api
│   ├── bot_lib.py
│   ├── bots_test_lib.py
│   ├── run.py
│   ├── test_bots
├── integrations
```

Each subdirectory in `bots` contains a bot. When developing bots, try to use the structure outlined
above as an orientation.

## How to run a bot

This guide will show you how to run a bot on a running Zulip
server.  It assumes you want to use one of the existing `api/bots`
bots in your Zulip organization.  If you want to write a new one, you
just need to write the `<my-bot>.py` script and put it into `/api/bots/<my-bot>` directory.

You need:

* An account in an organization on a Zulip server
  (e.g. [chat.zulip.org](https://chat.zulip.org) or
  yourSubdomain.zulipchat.com, or your own development server).
  Within that Zulip organization, users will be able to interact with
  your bot.
* A computer where you're running the bot from, with a clone of the
  [Zulip repository](https://github.com/zulip/zulip), which contains
  the bot library code in its `api/bots_api/<my-bot>` subdirectory. This is
  required to run your bot. The following instructions assume this
  repository to be located in `~/zulip/`.

**Note: Please be considerate when testing experimental bots on
  public servers such as chat.zulip.org.**

1. Register a new bot user on the Zulip server's web interface.

    * Log in to the Zulip server.
    * Navigate to *Settings* -> *Your bots* -> *Add a new bot*, fill
      out the form and click on *Create bot*.
    * A new bot user should appear in the *Your bots* panel.

2. Download the bot's `zuliprc` configuration file to your computer.

    * In the *Your bots* panel, click on the green icon to download
      its configuration file *zuliprc* (the structure of this file is
      explained [here](#configuration-file).)
    * Copy the file to a destination of your choice, e.g. to `~/.zuliprc`
      or `~/zuliprc-test`. Note that the destination should be accessible
      from your Zulip dev environment (e.g. Vagrant or Digital Ocean).

3. Subscribe the bot to the streams that the bot needs to interact with.

    * To subscribe your bot to streams, navigate to *Manage
      Streams*. Select a stream and add your bot by its email address
      (the address you assigned in step 1).
    * Now, the bot can do its job on the streams you subscribed it to.
    * (In future versions of the API, this step may not be required).

4. Run the bot.

    * In your Zulip repository, navigate to `~/zulip/api/bots_api/`
    * Run
      ```
      python run.py ../bots/<my-bot>/<my-bot>.py --config-file ~/.zuliprc`
      ```
      (using the path to the `.zuliprc` file from step 2).
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

## How to develop a bot

The tutorial below explains the structure of a bot `<my-bot>.py`,
which is the only file you need to create to develop a new bot. You
can use this as boilerplate code for developing your own bot.

Every bot is built upon this structure:

```
class MyBotHandler(object):
    '''
    A docstring documenting this bot.
    '''

    def usage(self):
        return '''Your description of the bot'''

    def handle_message(self, message, client, state_handler):
        # add your code here

handler_class = MyBotHandler
```

* The class name (in this case *MyBotHandler*) can be defined by you
  and should match the name of your bot. To register your bot's class,
  adjust the last line `handler_class = MyBotHandler` to match your
  class name.

* Every bot needs to implement the functions
    * `usage(self)`
    * `handle_message(self, message, client)`

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

*handle_message(self, message, client)*

handles user message.

#### Arguments

* self - the instance the method is called on.

* message - a dictionary describing a Zulip message

* client - used to interact with the server, e.g. to send a message

* state_handler - used to save states/information of the bot **beta**
    * use `state_handler.set_state(state)` to set a state (any object)
    * use `state_handler.get_state()` to retrieve the state set; returns a `NoneType` object if no state is set

#### Return values

None.

#### Example implementation

 ```
  def handle_message(self, message, client, state_handler):
     original_content = message['content']
     original_sender = message['sender_email']
     new_content = original_content.replace('@followup',
                                            'from %s:' % (original_sender,))

     client.send_message(dict(
         type='stream',
         to='followup',
         subject=message['sender_email'],
         content=new_content,
     ))
 ```
### client.send_message

*client.send_message(message)*

will send a message as the bot user.  Generally, this is less
convenient than *send_reply*, but it offers additional flexibility
about where the message is sent to.

### Arguments

* message - a dictionary describing the message to be sent by the bot

### Example implementation

```
client.send_message(dict(
    type='stream', # can be 'stream' or 'private'
    to=stream_name, # either the stream name or user's email
    subject=subject, # message subject
    content=message, # content of the sent message
))
```

### client.send_reply

*client.send_reply(message, response)*

will reply to the triggering message to the same place the original
message was sent to, with the content of the reply being *response*.

### Arguments

* message - Dictionary containing information on message to respond to
 (provided by `handle_message`).
* response - Response message from the bot (string).

### client.update_message

*client.update_message(message)*

will edit the content of a previously sent message.

### Arguments

* message - dictionary defining what message to edit and the new content

### Example

From `/zulip/api/bots/incrementor/incrementor.py`:

```
client.update_message(dict(
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
    * Ensure that you bot script is located in zulip/api/bots/<my-bot>/
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot:
      ```
      source /srv/zulip-py3-venv/bin/activate
      ```
      Note that you can switch back to a Python 2 environment as follows:
      ```
      source /srv/zulip-venv/bin/activate
      ```

* My bot works only on some streams.
    * Subscribe your bot to other streams, as described [here](#how-to-run-a-bot).

## Future direction

The long-term plan for this bot system is to allow the same
`BotHandler` code to eventually be usable in several contexts:

* Run directly using the Zulip `call_on_each_message` API, which is
  how the implementation above works.  This is great for quick
  development with minimal setup.
* Run in a simple Python webserver server, processing messages
  received from Zulip's outgoing webhooks integration.
* For bots merged into the mainline Zulip codebase, enabled via a
  button in the Zulip web UI, with no code deployment effort required.
