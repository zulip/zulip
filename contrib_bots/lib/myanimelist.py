import requests, logging
from xml.etree import ElementTree

# Signup for a MAL account here https://myanimelist.net/register.php?from=%2F
USERNAME = '[PLEASE CHANGE]'
PASSWORD = '[PLEASE CHANGE]'

# See myanimelist/docs.md for instructions on running this code.
MAL_SEARCH_URL = "https://myanimelist.net/api/anime/search.xml"
MAL_PAGE_URL = "https://myanimelist.net/anime/"

# Checks if the username and password has been changed
if USERNAME == "[PLEASE CHANGE]" or PASSWORD == "[PLEASE CHANGE]":
    logging.error("Please update the USERNAME and PASSWORD on contrib_bots/lib/mal.py")
    exit()

class MyanimelistHandler(object):
    '''
    This plugin responds with the link of to the anime's
    myanimelist page and some details along with
    it in the same stream and topic
    It looks for messages starting with '@mal'
    '''
    def search(self, query):
        # Encode query into url
        data = {
            'q': query
        }
        try:
            response = requests.get(MAL_SEARCH_URL, params=data, auth=(USERNAME, PASSWORD))
        except requests.exceptions.ConnectionError:
            logging.warning("Can not connect to myanimelist server.")
        except:
            logging.warning("An unknown error has occured when trying to get data.")
        try:
            xml = ElementTree.fromstring(response.content).find('entry')
            content_dict = {
                'id': '',
                'score': '',
                'type': '',
                'episodes': '',
                'status': '',
                'title': '',
            }
            for key in content_dict:
                content_dict[key] = xml.find(key).text
                # Makes sure that the key has a value
                if not content_dict[key]:
                    logging.error("Can't find value for %s when quering for %s" % (content_dict[key], query))
                    return None, False
            return content_dict, True
        except:
            logging.error("An unknown error has occured when parsing XML data.")
            return None, False

    def usage(self):
        return '''
            This plugin responds with myanimelist link and
            some details.
            Users should preface messages with '@mal'
            '''

    def triage_message(self, message):
        # return True if we want to (possibly) response to this message
        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting MAL responses
        if message['sender_full_name'] == 'mal-bot':
            return False
        is_mal = original_content.startswith('@mal')
        return is_mal

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_stream = message['display_recipient']
        original_topic = message['subject']

        content_dict, passed = self.search(original_content.replace('@mal ', ''))
        if passed:
            content = '[%s](%s)\n%s %s | %s' % (content_dict['title'],
                                                MAL_PAGE_URL + content_dict['id'],
                                                content_dict['type'],
                                                '(%s)' % (content_dict['episodes']),
                                                'Scored ' + content_dict['score'])
        else:
            content = "Sorry! No anime found :("
        client.send_message(dict(
            type='stream',
            to=[original_stream],
            subject=original_topic,
            content=content
        ))

handler_class = MyanimelistHandler
