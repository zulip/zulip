import requests
from xml.etree import ElementTree

# Signup for a MAL account here https://myanimelist.net/register.php?from=%2F
USERNAME = '[PLEASE CHANGE]'
PASSWORD = '[PLEASE CHANGE]'

# See docs.md for instructions on running this code.
MAL_SEARCH_URL = "https://myanimelist.net/api/anime/search.xml?q="
MAL_PAGE_URL = "https://myanimelist.net/anime/"

class LinksHandler(object):
    def search(self, query):
        response = requests.get(MAL_SEARCH_URL + query, auth=(USERNAME, PASSWORD))
        try:
            xml = ElementTree.fromstring(response.content).find('entry')
            contentDict = {
                'id': '',
                'score': '',
                'type': '',
                'episodes': '',
                'status': '',
                'title': '',
            }
            for key, value in contentDict.items():
                contentDict[key] = xml.find(key).text
                if not contentDict[key]:
                    return None, False
            return contentDict, True
        except:
            return None, False
    '''
    This plugin responds with the link of to the anime's
    myanimelist page and some details along with it
    It looks for messages starting with '@mal'
    '''

    def usage(self):
        if USERNAME == "[PLEASE CHANGE]" or PASSWORD == "[PLEASE CHANGE]":
            print("Please update the USERNAME and PASSWORD on contrib_bots/lib/mal.py")
            exit()
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
        is_mal = (original_content.startswith('@mal'))
        return is_mal

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_stream = message['display_recipient']
        original_topic = message['subject']

        contentDict, passed = self.search(original_content.replace('@mal ', ''))
        if passed:
            content = '[%s](%s)\n%s %s | %s' % (contentDict['title'],
                                                MAL_PAGE_URL + contentDict['id'],
                                                contentDict['type'],
                                                '(%s)' % (contentDict['episodes']),
                                                'Scored ' + contentDict['score'])
        else:
            content = "Sorry! No anime found :("
        client.send_message(dict(
            type='stream',
            to=[original_stream],
            subject=original_topic,
            content=content
        ))

handler_class = LinksHandler
