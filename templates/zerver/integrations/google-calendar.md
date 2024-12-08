# Zulip Google Calendar integration

Get Google Calendar reminders in Zulip! This is a great way to see
your reminders directly in your Zulip feed.

{start_tabs}

1.  {!download-python-bindings.md!}

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

1.  Run the command:

    `python /usr/local/share/zulip/integrations/google/get-google-credentials`

    Authorize access in the browser window that opens. If no browser opens,
    follow terminal prompts.

1.  In the same directory, run the command:

    `python /usr/local/share/zulip/integrations/google/gcal-bot --user foo@bar.com`

    Pass your Zulip user email address to the `--user` flag.

!!! tip ""

    To receive reminders, ensure the bot is running in an open terminal
    window. Consider using `screen`.

{end_tabs}

{!congrats.md!}

![Calendar demo](/static/images/integrations/google/calendar/003.png)

### Configuration Options

There are two optional flags that you can specify when running this
bot:

* `--calendar`: Specify the `calendar ID` of the Google calendar to get
  events from.

* `--interval`: Specify how many minutes in advance you want reminders
  delivered.

[google-quickstart]: https://developers.google.com/google-apps/calendar/quickstart/python
[google-api-client]: https://developers.google.com/calendar/api/quickstart/python#install_the_google_client_library
