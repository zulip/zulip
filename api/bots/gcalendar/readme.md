# Google Calendar bot

This bot facilitates creating Google Calendar events.

## Setup

1. Register a new project in the
   [Google Developers Console](https://console.developers.google.com/start).
2. Download the project's "client secret" JSON file to a path of your choosing.
3. Go to `<zulip_root>/api/integrations/google/`.
4. Run the Google OAuth setup script:

    ```bash
    $ python oauth.py \
        --secret_path <your_client_secret_file_path> \
        --credential_path <your_credential_path> \
        -s https://www.googleapis.com/auth/calendar
    ```

   The `--secret_path` must match wherever you stored the client secret
   downloaded in step 2, but the `--credential_path` can be any of your choice.
   If you don't specify the latter, it will be set to
   `~/.google_credentials.json` by default.

   Please note that if you set a path different to `~/.google_credentials.json`
   as the `--credential_path`, you have to modify the `CREDENTIAL_PATH`
   constant in the bot's `gcalendar.py` file.
5. Install the required dependencies:

    ```bash
    $ pip install --upgrade google-api-python-client dateparser
    ```
6. Prepare your `.zuliprc` file and run the bot itself, as described in
   ["How to run a bot"](http://zulip.readthedocs.io/en/latest/bots-guide.html#how-to-run-a-bot).

## Usage

For delimited events:

    @gcalendar <event_title> | <start_date> | <end_date> | <timezone> (optional)

For full-day events:

    @gcalendar <event_title> | <start_date>

For detailed help:

    @gcalendar help

Here are some examples:

    @gcalendar Meeting with John | 2017/03/14 13:37 | 2017/03/14 15:00:01 | EDT
    @gcalendar Comida | en 10 minutos | en 2 horas
    @gcalendar Trip to LA | tomorrow


Some additional considerations:

- If an ambiguous date format is used, **the American one will have preference**
  (`03/01/2016` will be read as `MM/DD/YYYY`). In case of doubt,
  [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) format is recommended
  (`YYYY/MM/DD`).
- If a timezone is specified in both a date and in the optional `timezone`
  field, **the one in the date will have preference**.
- You can use **different languages and locales** for dates, such as
  `Martes 14 de enero de 2003 a las 13:37 CET`. Some (but not all) of them are:
  English, Spanish, Dutch and Russian. A full list can be found
  [here](https://dateparser.readthedocs.io/en/latest/#supported-languages).
- The default timezone is **the server\'s**. However, it can be specified at
  the end of each date, in both numerical (`+01:00`) or abbreviated format
  (`CET`).
