# -*- coding: utf-8 -*-
from future import standard_library # You would need to download future.
standard_library.install_aliases()
import json
import urllib.request, urllib.parse, urllib.error

BASE_URL = 'https://api.spotify.com/v1/search?q='

class SpotifyHandler(object):
    '''
    This bot will allow users to directly search
    for songs, artists, and albums using the Spotify API.
    It can be called using `@spotify song/artist/album <your_search_query>`
    '''
    def handle_message(self, message, client, state_handler):
        def usage(self):
            return '''
            This bot will allow users to directly search
            for songs, artists, and albums using the Spotify API.
            It can be called using `@spotify song/artist/album <your_search_query>`
            This will return the top 10 search results from Spotify for either
            song/artist/album.
                '''

        def triage_message(self, message):
            # return True iff we want to (possibly) response to this message
            original_content = message['content']
            # This next line of code is defensive, as we
            # never want to get into an infinite loop of posting follow
            # ups for own follow ups!
            if message['display_recipient'] == 'spotify':
                return False
            is_spotify = original_content.startswith('@spotify')

            return is_spotify

        def get_data(query_type, original_content):
            new_content = ""
            if query_type == "song":
                content_limit = 5
                query_type = "track"
            elif query_type == "album":
                content_limit = 6
            elif query_type == "artist":
                content_limit = 7
            elif query_type == "playlist":
                content_limit = 9

            encoded_message = urllib.parse.quote(original_content[content_limit:])
            url = "{}{}&type={}&limit=10".format(BASE_URL, encoded_message, query_type)
            new_content += " Here are the {} with \"{}\" in them: ".format(query_type, original_content[content_limit:])
            return (new_content, urllib.request.urlopen(url).read())

        def get_data_multiple_parameters(query_data):
            url = BASE_URL
            for parameter in query_data:
                url += "{}:{}%20".format(parameter[0], parameter[1])
            url += "&type={}&limit=10".format(query_data[0][0])
            return urllib.request.urlopen(url).read()

        def artist_content(artist):
            artist_name = artist['name']
            artist_url = artist['external_urls']['spotify']
            return "\n [{}]({}) \n".format(artist_name, artist_url)

        def playlist_content(playlist):
            playlist_name = playlist['name']
            playlist_url = playlist['external_urls']['spotify']
            return "\n [{}]({}) \n".format(playlist_name, playlist_url)

        def album_content(album):
            album_name = album['name']
            album_url = album['external_urls']['spotify']
            artist_name = album['artists'][0]['name']
            artist_url = album['artists'][0]['external_urls']['spotify']
            return "\n [{}]({}) by [{}]({})\n".format(album_name, album_url, artist_name, artist_url)

        def track_content(track):
            song_name = track['name']
            song_url = track['external_urls']['spotify']
            album_name = track['album']['name']
            album_url = track['album']['external_urls']['spotify']
            artist_name = track['artists'][0]['name']
            artist_url = track['artists'][0]['external_urls']['spotify']
            return "\n [{}]({}) from the album [{}]({}) by [{}]({})\n".format(
                                                                            song_name,
                                                                            song_url,
                                                                            album_name,
                                                                            album_url,
                                                                            artist_name,
                                                                            artist_url,
                                                                            )
        original_content = message['content']
        original_content = original_content.replace('@spotify ', '')
        queries = original_content.split(",")
        new_content = ''
        if len(queries) > 1:
            query_data = []
            new_content = "Search results for "
            for original_content in queries:
                if original_content[0] == " ":
                    original_content = original_content[1:]
                query_action = original_content.split(' ')[0]
                if query_action == "album":
                    query_content = original_content[6:]
                elif query_action == "song":
                    query_content = original_content[5:]
                    query_action = "track"
                elif query_action == "artist":
                    query_content = original_content[7:]
                elif query_action == "playlist":
                    query_content = original_content[9:]
                new_content += "{} with name matching \"{}\" and ".format(query_action, query_content)
                query_data.append([query_action, query_content])
            raw_data = get_data_multiple_parameters(query_data)
            original_content_action = query_data[0][0]
            new_content = new_content[:-4]+":"

        else:
            if original_content[0] == " ":
                original_content = original_content[1:]
            original_content_action = original_content.split(' ')[0]
        if original_content_action == "album":
            if len(queries) < 1:
                new_content, raw_data = get_data("album", original_content)

            try:
                raw_albums_list = json.loads(raw_data)['albums']['items']
                if raw_albums_list == []:
                    new_content = "Sorry, we couldn't find anything for your search. :/"
                else:
                    for album in raw_albums_list:
                        new_content += album_content(album)

            except KeyError:
                new_content = "Sorry, something went wrong. Please try again later."
        elif original_content_action == "artist":
            if len(queries) < 1:
                new_content, raw_data = get_data("album", original_content)
            try:
                json_data = json.loads(raw_data)['artists']['items']
                if json_data == []:
                        new_content = "Sorry, we couldn't find anything for your search. :/"
                else:
                    for artist in json_data:
                        new_content += artist_content(artist)

            except KeyError:
                new_content = "Sorry, something went wrong. Please try again later."
        elif original_content_action == "song" or (original_content_action == "track"):
            if len(queries) < 1:
                new_content, raw_data = get_data("album", original_content)
            try:
                json_data = json.loads(raw_data)['tracks']['items']
                if json_data == []:
                    new_content = "Sorry, we couldn't find anything for your search. :/"
                else:
                    for track in json_data:
                        new_content += track_content(track)

            except KeyError:
                new_content = "Sorry, something went wrong. Please try again later."
        elif original_content_action == "playlist":
            if len(queries) == 1:
                new_content += " Here are playlists with \"{}\" in them: ".format(original_content[9:])
                raw_data = get_data("playlist", original_content)
            try:
                json_data = json.loads(raw_data)['playlists']['items']
                if json_data == []:
                    new_content = "Sorry, we couldn't find anything for your search. :/"
                else:
                    for playlist in json_data:
                        new_content += playlist_content(playlist)

            except KeyError:
                new_content = "Sorry, something went wrong. Please try again later."
        else:
            new_content = """I didn't quite get that. :/ \n please make sure your message follows this format \n
            `@spotify album/song/artist  <your_search_query>`\nor\n @spotify song  <song_name>, artist <artist_name>"""

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject = message['subject'],
            content=new_content,
        ))

handler_class = SpotifyHandler
