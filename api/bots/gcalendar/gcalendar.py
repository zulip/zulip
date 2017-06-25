import httplib2
import json
import logging
import os
import sys

# Uses Google's Client Library
#   pip install --upgrade google-api-python-client
from apiclient import discovery, errors
from oauth2client.client import HttpAccessTokenRefreshError
from oauth2client.file import Storage

# pip install --upgrade dateparser
import dateparser

from pytz.exceptions import UnknownTimeZoneError
from tzlocal import get_localzone

# Avoid cache-related warnings
# https://github.com/google/google-api-python-client/issues/299
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

# Modify this to match where your credentials are stored.
# It should be the same path you used in the
# '--credential_path' argument, when running the script
# in "api/integrations/google/oauth.py".
#
# $ python api/integrations/google/oauth.py \
#   --secret_path <your_client_secret_file_path> \
#   --credential_path <your_credential_path> \
#   -s https://www.googleapis.com/auth/calendar
#
# If you didn't specify any, it should be in the default
# path (~/.google_credentials.json)
CREDENTIAL_PATH = '~/.google_credentials.json'

class MessageParseError(Exception):
    def __init__(self, error_id):
        self.error_id = error_id

        details = ''

        if error_id == 1:
            details = 'Unknown message format'
        elif error_id == 2:
            details = 'Unknown date format'
        elif error_id == 3:
            details = 'The specified timezone doesn\'t exist'

        self.message = details

    def __str__(self):
        return self.message

def parse_message(message):
    '''
    Identifies and parses the different parts of a message sent to the bot

    Returns:
        Values, a tuple that contains the 2 (or 3) parameters of the message
    '''
    try:
        splits = message.split('|')
        title = splits[0].strip()

        settings = {
            'RETURN_AS_TIMEZONE_AWARE': True
        }

        if len(splits) == 4:  # Delimited event with timezone
            settings['TIMEZONE'] = splits[3].strip()

        start_date = dateparser.parse(splits[1].strip(), settings=settings)
        end_date = None

        if len(splits) >= 3:  # Delimited event
            end_date = dateparser.parse(splits[2].strip(), settings=settings)

            if not start_date.tzinfo:
                start_date = start_date.replace(tzinfo=get_localzone())
            if not end_date.tzinfo:
                end_date = end_date.replace(tzinfo=get_localzone())

        # Unknown date format
        if not start_date or len(splits) >= 3 and not end_date:
            raise MessageParseError(2)

        # Notice there isn't a "full day event with timezone", because the
        # timezone is irrelevant in that type of events
    except IndexError as e:
        logging.exception(e)
        raise MessageParseError(1)
    except UnknownTimeZoneError as e:
        logging.exception(e)
        raise MessageParseError(3)

    return title, start_date, end_date

def send_help_message(message, bot_handler):
    msg = ('This **Google Calendar bot** allows you to create events in your '
           'Google account\'s calendars.\n\n'
           'For example, if you want to create a new event, use:\n\n'
           '    @gcalendar <event_title> | <start_date> | <end_date> | '
           '<timezone> (optional)\n'
           'And for full-day events:\n\n'
           '    @gcalendar <event_title> | <date>\n'
           'Please notice that pipes (`|`) *cannot* be used in the input '
           'parameters.\n\n'
           'Here are some usage examples:\n\n'
           '    @gcalendar Meeting with John | 2017/03/14 13:37 | 2017/03/14 '
           '15:00:01 | EDT\n'
           '    @gcalendar Comida | en 10 minutos | en 2 horas\n'
           '    @gcalendar Trip to LA | tomorrow\n'
           '---\n'
           'Here is some information about how the dates work:\n'
           '* If an ambiguous date format is used, **the American one will '
           'have preference** (`03/01/2016` will be read as `MM/DD/YYYY`). In '
           'case of doubt, [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) '
           'format is recommended (`YYYY/MM/DD`).\n'
           '* If a timezone is specified in both a date and in the optional '
           '`timezone` field, **the one in the date will have preference**.\n'
           '* You can use **different languages and locales** for dates, such '
           'as `Martes 14 de enero de 2003 a las 13:37 CET`. Some (but not '
           'all) of them are: English, Spanish, Dutch and Russian. A full '
           'list can be found [here](https://dateparser.readthedocs.io/en/'
           'latest/#supported-languages).\n'
           '* The default timezone is **the server\'s**. However, it can be'
           'specified at the end of each date, in both numerical (`+01:00`) '
           'or abbreviated format (`CET`).')

    bot_handler.send_reply(message, msg)

def send_parsing_error_message(err, message, bot_handler):
    error = ''

    if err.error_id == 1:
        error = ('Unknown message format.\n\n'
                 'Usage examples:\n\n'
                 '    @gcalendar Meeting with John | 2017/03/14 13:37 | '
                 '2017/03/14 15:00:01 | GMT\n'
                 '    @gcalendar Trip to LA | tomorrow\n'
                 'Send `@gcalendar help` for detailed usage instructions.')
    elif err.error_id == 2:
        error = ('Unknown date format.\n\n'
                 'Send `@gcalendar help` for detailed usage instructions.')
    elif err.error_id == 3:
        error = ('Unknown timezone.\n\n'
                 'Please, use a numerical (`+01:00`) or abbreviated (`CET`) '
                 'timezone.\n'
                 'Send `@gcalendar help` for detailed usage instructions.')

    bot_handler.send_reply(message, error)

class GCalendarHandler(object):
    '''
    This plugin facilitates creating Google Calendar events.

    Usage:
        For delimited events:
            @gcalendar <event_title> | <start_date> | <end_date> | <timezone> (optional)
        For full-day events:
            @gcalendar <event_title> | <start_date>

    The "event-title" supports all characters but pipes (|)

    Timezones can be specified in both numerical (+00:00) or abbreviated
    format (UTC).
    The timezone of the server will be used if none is specified.

    Right now it only works for the calendar set as "primary" in your account.

    Please, run the script "api/integrations/google/oauth.py" before using this
    bot in order to provide it the necessary access to your Google account.
    '''
    def __init__(self):
        # Attempt to gather the credentials
        credentials = None
        try:
            store = Storage(os.path.expanduser(CREDENTIAL_PATH))
            credentials = store.get()
        except IOError:
            logging.error('Couldn\'t find valid credentials.\n'
                          'Run the oauth.py script in'
                          '"api/integrations/google/oauth.py" first.')
            sys.exit(1)

        # Create the Google Calendar service, once the bot is
        # successfully authorized
        http = credentials.authorize(httplib2.Http())
        self.service = discovery.build('calendar', 'v3', http=http)

    def usage(self):
        return '''
            This plugin will allow users to create events
            in their Google Calendar. Users should preface
            messages with "@gcalendar".

            Before running this, make sure to register a new
            project in the Google Developers Console
            (https://console.developers.google.com/start/api?id=calendar),
            download the "client secret" as a JSON file, and run
            "api/integrations/google/oauth.py" for the Calendar
            read-write scope
            (https://www.googleapis.com/auth/calendar).
            '''

    def handle_message(self, message, bot_handler, state_handler):

        content = message['content'].strip()
        if content == 'help':
            send_help_message(message, bot_handler)
            return

        try:
            title, start_date, end_date = parse_message(content)
        except MessageParseError as e:  # Something went wrong during parsing
            send_parsing_error_message(e, message, bot_handler)
            return

        event = {
            'summary': title
        }

        if not end_date:  # Full-day event
            date = start_date.strftime('%Y-%m-%d')
            event.update({
                'start': {'date': date},
                'end': {'date': date}
            })
        else:
            event.update({
                'start': {'dateTime': start_date.isoformat()},
                'end': {'dateTime': end_date.isoformat()}
            })

            try:
                event['start'].update({'timeZone': start_date.tzinfo.zone})
                event['end'].update({'timeZone': end_date.tzinfo.zone})
            except AttributeError:
                pass

        try:
            # TODO: Choose calendar ID from somewhere
            event = self.service.events().insert(calendarId='primary',
                                                 body=event).execute()
        except errors.HttpError as e:
            err = json.loads(e.content.decode('utf-8'))['error']

            error = ':warning: **Error!**\n'

            if err['code'] == 400:  # There's something wrong with the input
                error += '\n'.join('* ' + problem['message']
                                   for problem in err['errors'])
            else:  # Some other issue not related to the user
                logging.exception(e)

                error += ('Something went wrong.\n'
                          'Please, try again or check the logs if the issue '
                          'persists.')

            bot_handler.send_reply(message, error)
            return
        except HttpAccessTokenRefreshError as e:
            logging.exception(e)

            error += ('The authorization token has expired.\n'
                      'The most probable cause for this is that the token has '
                      'been revoked.\n'
                      'The bot will now stop. Please, run the oauth.py script '
                      'again to go through the OAuth process and provide it '
                      'with new credentials.')

            bot_handler.send_reply(message, error)
            sys.exit(1)

        if not title:
            title = '(Untitled)'

        date_format = '%c %Z'

        start_str = start_date.strftime(date_format)
        end_str = None

        if not end_date:
            reply = (':calendar: Full day event created!\n'
                     '> **{title}**, on *{startDate}*')

        else:
            end_str = end_date.strftime(date_format)
            reply = (':calendar: Event created!\n'
                     '> **{title}**, from *{startDate}* to *{endDate}*')

        bot_handler.send_reply(message,
                               reply.format(title=title,
                                            startDate=start_str.strip(),
                                            endDate=end_str))

handler_class = GCalendarHandler

def test():
    # These tests only check that the message parser works properly, since
    # testing the other features in the bot require interacting with the Google
    # Calendar API.
    msg = 'Go to the bank | Monday, 21 Oct 2014'
    title, start_date, end_date = parse_message(msg)
    assert title == 'Go to the bank'
    assert start_date.strftime('%Y-%m-%d') == '2014-10-21'
    assert end_date is None

    msg = ('Meeting with John | '
           'Martes 14 de enero de 2003 a las 13:37:00 CET | '
           'Martes 14 de enero de 2003 a las 15:01:10 CET')
    title, start_date, end_date = parse_message(msg)
    assert title == 'Meeting with John'
    assert start_date.isoformat() == '2003-01-14T13:37:00+01:00'
    assert end_date.isoformat() == '2003-01-14T15:01:10+01:00'

    msg = 'Buy groceries | someday'
    ex_message = ''
    try:
        title, start_date, end_date = parse_message(msg)
    except MessageParseError as e:
        ex_message = e.message
    assert ex_message == 'Unknown date format'

if __name__ == '__main__':
    test()
