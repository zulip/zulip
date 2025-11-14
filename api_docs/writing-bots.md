# Writing interactive bots

This guide is about writing and testing interactive bots. We assume
familiarity with our [guide for running bots](running-bots).

On this page you'll find:

* A step-by-step
  [guide](#installing-a-development-version-of-the-zulip-bots-package)
  on how to set up a development environment for writing bots with all
  of our nice tooling to make it easy to write and test your work.
* A [guide](#writing-a-bot) on writing a bot.
* A [guide](#adding-a-bot-to-zulip) on adding a bot to Zulip.
* Common [problems](#common-problems) when developing/running bots and their solutions.

## Installing a development version of the Zulip bots package

{start_tabs}

1. Clone the [python-zulip-api](https://github.com/zulip/python-zulip-api)
   repository:

    ```
    git clone https://github.com/zulip/python-zulip-api.git
    ```

1. Navigate into your cloned repository:

    ```
    cd python-zulip-api
    ```

1. Install all requirements in a Python virtualenv:

    ```
    python3 ./tools/provision
    ```

1. Run the command provided in the final output of the `provision` process to
   enter the new virtualenv. The command will be of the form `source .../activate`.

1. You should now see the name of your virtualenv preceding your prompt (e.g.,
   `(zulip-api-py3-venv)`).

!!! tip ""

    `provision` installs the `zulip`, `zulip_bots`, and
    `zulip_botserver` packages in developer mode. This enables you to
    modify these packages and then run your modified code without
    having to first re-install the packages or re-provision.

{end_tabs}

## Writing a bot

The tutorial below explains the structure of a bot `<my-bot>.py`,
which is the only file you need to create for a new bot. You
can use this as boilerplate code for developing your own bot.

Every bot is built upon this structure:

```python
class MyBotHandler(object):
    '''
    A docstring documenting this bot.
    '''

    def usage(self):
        return '''Your description of the bot'''

    def handle_message(self, message, bot_handler):
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

## Adding a bot to Zulip

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
    │       ├───requirements.txt
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

Each subdirectory in `bots` contains a bot. When writing bots, try to use the structure outlined
above as an orientation.

## Testing a bot's output

If you just want to see how a bot reacts to a message, but don't want to set it up on a server,
we have a little tool to help you out: `zulip-bot-shell`

* [Install all requirements](#installing-a-development-version-of-the-zulip-bots-package).

* Run `zulip-bot-shell` to test one of the bots in
  [`zulip_bots/bots`](https://github.com/zulip/python-zulip-api/tree/main/zulip_bots/zulip_bots/bots).

Example invocations are below:

```
> zulip-bot-shell converter

Enter your message: "12 meter yard"
Response: 12.0 meter = 13.12336 yard

> zulip-bot-shell -b ~/followup.conf followup

Enter your message: "Task completed"
Response: stream: followup topic: foo_sender@zulip.com
          from foo_sender@zulip.com: Task completed

```

Note that the `-b` (aka `--bot-config-file`) argument is for an optional third party
config file (e.g., ~/giphy.conf), which only applies to certain types of bots.

## Common problems

* I modified my bot's code, yet the changes don't seem to have an effect.
    * Ensure that you restarted the `zulip-run-bot` script.

* My bot won't start
    * Ensure that your API config file is correct (download the config file from the server).
    * Ensure that you bot script is located in `zulip_bots/bots/<my-bot>/`
    * Are you using your own Zulip development server? Ensure that you run your bot outside
      the Vagrant environment.
    * Some bots require Python 3. Try switching to a Python 3 environment before running
      your bot.

## Future direction

The long-term plan for this bot system is to allow the same
`ExternalBotHandler` code to eventually be usable in several contexts:

* Run directly using the Zulip `call_on_each_message` API, which is
  how the implementation above works.  This is great for quick
  development with minimal setup.
* Run in a simple Python web server, processing messages
  received from Zulip's outgoing webhooks integration.
* For bots merged into the mainline Zulip codebase, enabled via a
  button in the Zulip web UI, with no code deployment effort required.

## Related articles

* [Interactive bots API](/api/interactive-bots-api)
* [Writing tests for bots](/api/writing-tests-for-interactive-bots)
* [Running bots](/api/running-bots)
* [Deploying bots](/api/deploying-bots)
* [Configuring the Python bindings](/api/configuring-python-bindings)
* [Non-webhook integrations](/api/non-webhook-integrations)
