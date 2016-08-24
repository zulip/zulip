# Overview

This is the documentation for an experimental new system for writing
bots that react to messages.

This directory contains library code for running Zulip
bots that react to messages sent by users.

This document explains how to run the code, and it also
talks about the architecture for creating bots.

## Design goals

The goal is to have a common framework for hosting a bot that reacts
to messages in any of the following settings:

* Run as a long-running process using `call_on_each_event`
  (implemented today).

* Run via a simple web service that can be deployed to PAAS providers
  and handles outgoing webhook requests from Zulip.

* Embedded into the Zulip server (so that no hosting is required),
  which would be done for high quality, reusable bots; we would have a
  nice "bot store" sort of UI for browsing and activating them.

## Running bots

Here is an example of running the "follow-up" bot from
inside a Zulip repo:

    cd ~/zulip/contrib_bots
    python run.py lib/followup.py --config-file ~/.zuliprc-prod

Once the bot code starts running, you will see a
message explaining how to use the bot, as well as
some log messages.  You can use the `--quiet` option
to suppress these messages.

The bot code will run continuously until you kill them with
control-C (or otherwise).

### Configuration

For this document we assume you have some prior experience
with using the Zulip API, but here is a quick review of
what a `.zuliprc` files looks like.  You can connect to the
API as your own human user, or you can go into the Zulip settings
page to create a user-owned bot.

    [api]
    email=someuser@example.com
    key=<your api key>
    site=https://zulip.somewhere.com

## Architecture

In order to make bot development easy, we separate
out boilerplate code (loading up the Client API, etc.)
from bot-specific code (do what makes the bot unique).

All of the boilerplate code lives in `../run.py`.  The
runner code does things like find where it can import
the Zulip API, instantiate a client with correct
credentials, set up the logging level, find the
library code for the specific bot, etc.

Then, for bot-specific logic, you will find `.py` files
in the `lib` directory (i.e. the same directory as the
document you are reading now).

Each bot library simply needs to do the following:

- Define a class that supports the methods `usage`,
`triage_message`, and `handle_message`.
- Set `handler_class` to be the name of that class.

(We make this a two-step process, so that you can give
a descriptive name to your handler class.)

## Portability

Creating a handler class for each bot allows your bot
code to be more portable.  For example, if you want to
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
server, then you can still use the full Zulip API.  The
hope, though, is that this architecture will make
writing simple bots a quick/easy process.

