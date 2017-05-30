# Contrib bots

This is the documentation for an experimental new system for writing
bots that react to messages. It explains how to run the code, and also
talks about the architecture for creating such bots.

This directory contains library code for running them.

## Design goals

The goal is to have a common framework for hosting a bot that reacts
to messages in any of the following settings:

* Run as a long-running process using `call_on_each_event`.

* Run via a simple web service that can be deployed to PAAS providers
  and handles outgoing webhook requests from Zulip.

* Embedded into the Zulip server (so that no hosting is required),
  which would be done for high quality, reusable bots; we would have a
  nice "bot store" sort of UI for browsing and activating them.

* Run locally by our technically inclined users for bots that require
  account specific authentication, for example: a gmail bot that lets
  one send emails directly through Zulip.

## Running bots

Here is an example of running the "follow-up" bot from
inside a Zulip repo (and in your remote instance):

    cd ~/zulip/api
    bots_api/run.py bots/followup/followup.py --config-file ~/.zuliprc-prod

Once the bot code starts running, you will see a
message explaining how to use the bot, as well as
some log messages. You can use the `--quiet` option
to suppress these messages.

The bot code will run continuously until you end the program with
control-C (or otherwise).

### Zulip configuration

For this document we assume you have some prior experience
with using the Zulip API, but here is a quick review of
what a `.zuliprc` files looks like. You can connect to the
API as your own human user, or you can go into the Zulip settings
page to create a user-owned bot.

    [api]
    email=someuser@example.com
    key=<your api key>
    site=https://zulip.somewhere.com

When you run your bot, make sure to point it to the correct location
of your `.zuliprc`.

### Third party configuration

If your bot interacts with a non-Zulip service, you may
have to configure keys or usernames or URLs or similar
information to hit the other service.

Do **NOT** put third party configuration information in your
`.zuliprc` file. Do not put third party configuration
information anywhere in your Zulip directory. Instead,
create a separate configuration file for the third party's
configuration in your home directory.

Any bots that require this will have instructions on
exactly how to create or access this information.

### Python dependencies

If your module requires Python modules that are not either
part of the standard Python library or the Zulip API
distribution, we ask that you put a comment at the top
of your bot explaining how to install the dependencies/modules.

Right now we don't support any kind of automatic build
environment for bots, so it's currently up to the users
of the bots to manage their dependencies. This may change
in the future.

## Architecture

In order to make bot development easy, we separate
out boilerplate code (loading up the Client API, etc.)
from bot-specific code (actions of the bot/what the bot does).

All of the boilerplate code lives in `../run.py`. The
runner code does things like find where it can import
the Zulip API, instantiate a client with correct
credentials, set up the logging level, find the
library code for the specific bot, etc.

Then, for bot-specific logic, you will find `.py` files
in the `lib` directory (i.e. the same directory as the
document you are reading now).

Each bot library simply needs to do the following:

- Define a class that supports the methods `usage`
and `handle_message`.
- Set `handler_class` to be the name of that class.

(We make this a two-step process to reduce code repetition
and to add abstraction.)

## Portability

Creating a handler class for each bot allows your bot
code to be more portable. For example, if you want to
use your bot code in some other kind of bot platform, then
if all of your bots conform to the `handler_class` protocol,
you can write simple adapter code to use them elsewhere.

Another future direction to consider is that Zulip will
eventually support running certain types of bots on
the server side, to essentially implement post-send
hooks and things of those nature.

Conforming to the `handler_class` protocol will make
it easier for Zulip admins to integrate custom bots.

In particular, `run.py` already passes in instances
of a restricted variant of the Client class to your
library code, which helps you ensure that your bot
does only things that would be acceptable for running
in a server-side environment.

## Other approaches

If you are not interested in running your bots on the
server, then you can still use the full Zulip API and run
them locally. The hope, though, is that this
architecture will make writing simple bots a quick/easy
process.
