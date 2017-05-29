# See readme.md for instructions on running this code.
import requests
from bs4 import BeautifulSoup


class YoutubeHandler(object):
    def usage(self):
        return '''
            This plugin will give you first video from youtube for selected query
            '''

    def handle_message(self, message, client, state_handler):
        help_content = '''
            To use Youtube Bot type search term after @mention-bot
            Example:
            @mention-bot funny cats
            '''.strip()
        # to stop the bot from spamming group chats
        if message['is_mentioned'] is True:
            if message['content'] == '':
                client.send_reply(message, help_content)
            else:
                text_to_search = message['content']
                url = "https://www.youtube.com/results?search_query=" + text_to_search
                r = requests.get(url)
                soup = BeautifulSoup(r.text, 'lxml')
                video_id = soup.find(attrs={'class': 'yt-uix-tile-link'})
                try:
                    link = 'https://www.youtube.com' + video_id['href']
                    client.send_reply(message, link)
                except TypeError:
                    client.send_reply(message, 'No video found for specified search terms')


handler_class = YoutubeHandler
