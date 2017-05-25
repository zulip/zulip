Before running this bot, make sure to get a Mashape API key.
Go to this link:
<https://market.mashape.com/community/urban-dictionary>
This is the API that powers the dictionary.

Click on the **Sign Up Free** button at the top and create
an account. Then click on the **Documentation** tab. Scroll down to the
bottom, and click on the **Test Endpoint** button.
This will add the Yoda Speak API to your default application. You can
also add it to a different application if you wish. Now click on the
**Applications** tab at the top. Select the application that you added
the Yoda Speak API to. Click on the blue **GET THE KEYS** button.

On the pop-up that comes up, click on the **COPY** button.
This is your Mashape API key. It is used
to authenticate. Store it in the `udlookup.config` file.

The `udlookup.config` file should be located at `~/udlookup.config`.

Example input:

    @mention-bot You will learn how to speak like me someday.

If you need help while the bot is running just input `@mention-bot help`.

## Running the bot

Here is an example of running the "udlookup" bot from
inside a Zulip repo:

    cd ~/zulip/contrib_bots
    ./run.py bots/udlookup/udlookup.py --config-file ~/.zuliprc-prod

Once the bot code starts running, you will see a
message explaining how to use the bot, as well as
some log messages.  You can use the `--quiet` option
to suppress some of the informational messages.

The bot code will run continuously until you kill them with
control-C (or otherwise).
