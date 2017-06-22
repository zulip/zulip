Get Google Calendar reminders in Zulip! This is a great way to see
your reminders directly in your Zulip feed.

{!download-python-bindings.md!}

This bot should be set up on a trusted machine, because your API
key is visible to local users through the command line or config
file.

Next, follow the instructions for **Step 1** at
[this link](https://developers.google.com/google-apps/calendar/quickstart/python)
to get a `client_secret` file. Save this file as `client_secret.json`
to your `~/` directory.

Next, install the latest Google API Client for Python by following the
instructions on the
[Google Website](https://developers.google.com/api-client-library/python/start/installation).

Then go to your **Zulip Settings** by clicking on the cog in the top
right corner, and then clicking on **Settings**.

Click on the tab that’s labeled **Your bots** and click on
**Show/change your API key**. Enter your password if prompted, and
download the `zuliprc` file. Save this file as `.zuliprc` to your `~/`
directory.

![](/static/images/integrations/google/calendar/001.png)

Run the `get-google-credentials` with this command:

    python /usr/local/share/zulip/integrations/google/get-google-credentials

It should open up a browser and ask you for certain permissions. Give
Zulip access, and move on to the next step. If it doesn’t open a
browser, follow the instructions in the terminal window.

Now, all that’s left to do is to run the `gcal-bot` script, in the
same directory as the `get-google-credentials` script, with the
necessary parameters:

    python /usr/local/share/zulip/integrations/google/gcal-bot --user foo@zulip.com

The `--user` flag specifies the user to send the reminder to.

There are two optional flags that you can specify when running this
script:

* `--calendar`: This flag specifies the calendar to watch from the
  user’s Google Account. By default, this flag is set to a user’s
  primary or default calendar. To specify a calendar, you need the
  calendar ID which can be obtained by going to Google Calendar and
  clicking on the wedge next to the calendar’s name. Click on settings
  in **Calendar settings** in the drop down, and look for the **Calendar
  Address** section. Copy the **Calendar ID** from the right side of the
  page and use that as the value for this flag.

![](/static/images/integrations/google/calendar/002.png)

* `--interval`: This flag specifies the interval of time - in
  minutes - between receiving the reminder, and the actual event. For
  example, an interval of 30 minutes would mean that you would receive a
  reminder for an event 30 minutes before it is scheduled to occur.

Don’t close the terminal window with the bot running (you can use
`screen` if needed). You will only get reminders if the bot is still
running.

{!congrats.md!}

![](/static/images/integrations/google/calendar/003.png)
