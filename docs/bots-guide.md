# Writing bots
**This feature is still experimental.**

The contrib_bots system is a new part of Zulip that allows
bot developers to write a large class of bots by simply reacting to messages.

With bots, you *can*

* intercept and view messages sent by users on Zulip
* send out new messages

With bots, you *cannot*

* modify an intercepted message (you have to send a new message)
* send messages on behalf of other users
* intercept private messages


On this page you'll find:

* A step-by-step [tutorial](#how-to-deploy-a-bot) on how to deploy a bot.
* A step-by-step [tutorial](#how-to-develop-a-bot) on how to develop a bot.
* A [documentation](#bot-api) of the bot API.
* Common [problems](#common-problems) when developing/deploying bots and their solutions.

Contributions to this guide are very welcome, so if you run into any
issues following these instructions or come up with any tips or tools
that help with writing bots, please visit the [Zulip chat](https://chat.zulip.org), open an issue, or submit a pull request
to share your ideas!

## How to deploy a bot
This guide will show you how to deploy a bot on your running Zulip server.
It presumes that you already have a fully implemented `<my-bot>.py` bot and now want to try it out.

1. Copy your bot `<my-bot>.py` to `~/zulip/contrib_bots/lib/`.

    * This is the place where all Zulip bots are stored.

    * You can also test out bots that already exist in this directory.

2. Run your Zulip server. Bots can only be deployed on running systems.

3. Register a new bot on your Zulip server's web interface.

    * Navigate to *Settings* -> *Your Bots* -> *Add a New Bot*, fill out the form and click on *Create Bot*.
    * A new bot should appear in the *Your Bots* panel.

4. Add the bot's configuration file on your Zulip server.

    * In the *Your Bots* panel, click on the green icon to download its configuration file *.zuliprc* (the structure of this file is explained [here](#configuration-file).
    * Copy the file to a destination of your choice on your Zulip server, e.g. to `~/.zuliprc` or `~/zuliprc-test`.

5. Subscribe the bot to the streams that the bot needs to read messages from or write messages to.

    * To subscribe your bot to streams, navigate to *Manage Streams*. Select a stream and add your bot by its email address (the address you assigned in step 3).
    * Now, the bot will do its job on the streams you subscribed it to.

6. Run the bot.

    * On your Zulip server (and outside the Vagrant environment), navigate to `~/zulip/contrib_bots/`
    * Run `python run.py ~/zulip/contrib_bots/lib/<my-bot>.py --config-file ~/.zuliprc`. The `~/` before `.zuliprc` should point to the directory containing the file (in this case, it is the home directory).
    * Check the output of the command. It should start with the text the `usage` function returns, followed by logging output similar to this:
    ```
    INFO:root:starting message handling...
    INFO:requests.packages.urllib3.connectionpool:Starting new HTTP connection (1): localhost
    ```
    * Congrats! Now, your bot should be ready to test on the streams you've subscribed it to.

### Test the `followup.py` bot
1. Do the previous steps for the `followup.py` bot.
2. Create the *followup* stream.
3. Subscribe the bot to the newly created *followup* stream and a stream you want to use it from, e.g. *social*.
4. Send a message to the stream you've subscribed the bot to (other than *followup*). If everything works, a copy of the message should now pop up in the *followup* stream.

## How to develop a bot

The tutorial below explains the structure of a bot `<my-bot>.py`. You can use this as boilerplate code for developing your own bot.

Every bot is built upon this structure:
```
class MyBotHandler(object):
    '''
    A docstring documenting this bot.
    '''

    def usage(self):
        return '''Your description of the bot'''

    def triage_message(self, message, client):
        #add your code here

    def handle_message(self, message, client, state_handler):
        # add your code here

handler_class = MyBotHandler
```
* The class name (in this case *MyBotHandler*) can be defined by you and should match the name of your bot. To register your bot's class, adjust the last line `handler_class = MyBotHandler` to match your class name.

* Every bot needs to implement the functions
    * `usage(self)`
    * `triage_message(self, message, client)`
    * `handle_message(self, message, client)`

* These functions are documented in the [next section](#bot-api).

## Bot API
This section documents the functions every bot needs to implement and the structure of the bot's config file.

### usage
*usage(self)*

is called to retrieve information about the bot.

#### Arguments
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

### triage_message
*triage_message(self, message, client)*

is called when a message was sent.

#### Arguments
* self - the instance the method is called on

* message - a dictionary containing information about the message, e.g.
    * content - the content of the message
    * content_type - the type of the content, e.g. *'text/x-markdown'* for normal messages
    * display_recipient - the name of the stream the message is sent to (string)
    * is_mentioned - is the bot pinged with an '@' in the message? (boolean)
    * sender_email - email of the sender (string)
    * sender_full_name - full name of the sender (string)
    * subject - topic of the message (string)
    * timestamp - when was the message sent (integer)

* client - contains information about this bot
    * client.full_name - name of the bot account
    * client.email - email of the bot account

#### Return values
 * True if the bot should react to this message
 * False otherwise

#### Example implementation
```
def triage_message(self, message, client):
original_content = message['content']
    if message['display_recipient'] == 'followup':
        return False
    is_follow_up = (original_content.startswith('@followup') or
                        original_content.startswith('@follow-up'))
    return is_follow_up
```

### handle_message
*handle_message(self, message, client)*

is called when `triage_message` returns true, handles user message.

#### Arguments
* self - the instance the method is called on.

* message - a dictionary describing a Zulip message

* client - used to interact with the server, e.g. to send a message
    * use client.send_message(message) to send a message

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

### Configuration file

 ```
 [api]
 key=<api-key>
 email=<email>
 site=<dev-url>
 ```

* key - the API key you created for the bot; this is how Zulip knows the request is from an authorized user.

* email - the email address of the bot, e.g. `some-bot@zulip.com`

* site - your development environment URL; if you are working on a development environment hosted on your computer, use `localhost:9991`

## Common problems
* I modified my bot's code, yet the changes don't seem to have an effect.
    * Ensure that you restarted the `run.py` script.

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that you bot script is located in zulip/contrib_bots/lib/

* My bot works only on some streams.
    * Subscribe your bot to other streams, as described [here](#how-to-deploy-a-bot).
