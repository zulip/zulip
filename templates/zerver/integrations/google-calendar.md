# Zulip Google Calendar integration

Get Google Calendar reminders in your Zulip DMs! This is a great way to see
your reminders directly in your Zulip feed.

!!! warn ""

    This bot should be set up on a trusted machine, because your API
    key is visible to local users through the command line or config
    file.

{start_tabs}

1.  Download and install our
    [Python bindings and example scripts](/api/installation-instructions).

1.  Install the requirements for the integration script with:

    `pip install /usr/local/share/zulip/integrations/google/requirements.txt`

1.  Follow [Google's instructions][google-quickstart] to get a
    `client_secret` file, and save it as `client_secret.json` in your
    `~/` directory.

1.  Install the latest Google API Client for Python by following [Google's
    instructions][google-api-client].

1.  In Zulip, click the **gear** (<i class="fa fa-cog"></i>) icon at the top
    right, select **Personal settings**. Select the **Account & privacy**
    tab, and click **Manage your API key**. Enter your password if prompted,
    download the `zuliprc` file, and save it as `.zuliprc` in your`~/`
    directory.

1.  To authorize your Zulip bot to view your Calendar, run the script:

    `python /usr/local/share/zulip/integrations/google/get-google-credentials`

    Authorize access in the browser window that opens. If no browser opens,
    follow the terminal prompts.

1.  In the same directory, start the Zulip bot with the command:

    `python /usr/local/share/zulip/integrations/google/google-calendar --user <your user email for Zulip>`

    Use the [optional flags](#configuration-options) to configure the bot.

1.  You will get reminders as long as the terminal session with the bot
    remains open. Consider using `screen` to run the bot in the background.

{end_tabs}

### Configuration Options

There are two optional flags that you can specify when running the
`google-calendar` bot:

* `--calendar`: Specify the `calendar ID` of the Google calendar to get
  events from. By default, the "primary" calendar is used.

* `--interval`: Specify how many minutes in advance you want reminders
  delivered. The default value is 30 minutes.

[google-quickstart]: https://developers.google.com/google-apps/calendar/quickstart/python
[google-api-client]: https://developers.google.com/calendar/api/quickstart/python#install_the_google_client_library
