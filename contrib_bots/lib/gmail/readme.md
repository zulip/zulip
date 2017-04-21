# Overview

This is the documentation for how to set up and run the Gmail bot. (`gmail.py`)

This bot will allow you to send an email from a Gmail account.

## Setup
Before running this bot, make sure to get a `.client_secret.json` file and store
it in your home directory. Follow the instructions for <b>Step 1</b> at
[this link](https://developers.google.com/gmail/api/quickstart/python) to get the right file.
<b>Important:</b> Make sure you save it as `.client_secret.json`.

This bot requires the `google-api-python-client` dependecy to run. It can be installed
by following the instructions for <b>Step 2</b> on
[this tutorial](https://developers.google.com/gmail/api/quickstart/python).

Next, run the google.py script in the `contrib_bots/lib/` directory from the command line.
This script gets authentication to use your Google account. Either a site will open up with
instructions, or you will be given a link in the command line and prompted to open it in a browser.

Create a bot from within Zulip that you want to use with this script and
download its .zuliprc file and save it to your
Home directory. It should look something like this:

    [api]
    email=someuser@example.com
    key=<your api key>
    site=https://zulip.somewhere.com

## Running the bot

This is how you run the Gmail bot:

    `cd ~/zulip/contrib_bots`
    `./run.py lib/gmail.py --config-file ~/.zuliprc`

Once the bot code starts running, you will see a
message explaining how to use the bot, as well as
some log messages.  You can use the `--quiet` option
to suppress some of the informational messages.

The bot code will run continuously until you kill it with
control-C (or otherwise).
