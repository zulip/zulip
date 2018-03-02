from typing import Any, Dict, Text, List
from django.http import HttpRequest, HttpResponse
from zerver.lib.actions import check_send_stream_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile
import requests
import json

# POSSIBLE UPGRADE : MESSAGE WHEN A FOLDER/FILE IS SHARED TO WHICH USER
#                  : Who updated the file/folder

# This cursor needs to be saved in a file
#    because a server restart will remove all saved cursors.
# Save past cursors of each user
cursors = dict()  # type: Dict[str, str]

def get_latest_cursor(access_token: str) -> Any:

    url = "https://api.dropboxapi.com/2/files/list_folder/get_latest_cursor"
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json"
    }
    data = {
        "path": "",
        "recursive": True,
        "include_media_info": True,
        "include_deleted": True
    }

    response = requests.post(url, headers=headers, data=json.dumps(data).encode()).json()

    if response.get('error') is not None:
        return 404

    return response

def get_paginated_list_of_folders(access_token: str, cursor: str) -> Dict[str, Any]:

    url = "https://api.dropboxapi.com/2/files/list_folder/continue"
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json"
    }
    data = {
        "cursor": cursor
    }
    response = requests.post(url, headers=headers, data=json.dumps(data).encode()).json()
    return response

def get_updated_files(access_token: str, user_email: str) -> List[str]:

    global cursors

    # Get the past cursor stored of the user
    cursor = cursors.get(user_email, None)  # type: str
    messages = []
    if cursor is None:
        # user hasn't verified the Webhook URL
        messages.append("Some changes were made in your dropbox account, "
                        + "verfiy your WEBHOOK URL to get detailed messages.")
        return messages

    has_more = True

    while has_more:
        # GET the changes after the last cursor
        response = get_paginated_list_of_folders(access_token, cursor)
        cursor = response['cursor']  # update the latest cursor
        for meta in response['entries']:

            if meta['.tag'] == 'file':  # IF FILE CHANGED
                messages.append('ADDED File : ' + meta['path_lower'])

            elif meta['.tag'] == 'folder':  # IF FOLDER CHANGED
                messages.append('ADDED Folder : ' + meta['path_lower'])

            elif meta['.tag'] == 'deleted':  # IF FILE/FOLDER DELETED
                messages.append('DELETED File/Folder : ' + meta['path_lower'])

        has_more = response['has_more']

    return messages

@api_key_only_webhook_view('Dropbox')
@has_request_variables
def api_dropbox_webhook(request: HttpRequest, user_profile: UserProfile,
                        stream: Text=REQ(default='test'),
                        topic: Text=REQ(default='Dropbox'),
                        access_token: Text=REQ(default=None)) -> HttpResponse:
    global cursors

    user_email = user_profile.email
    if access_token is None:
        return HttpResponse("Please append &access_token=<ACCESSTOKEN> at the end of your Webhook URL.")

    if request.method == 'GET':
        # Dropbox gives us 10s to return 'challenge' which is sufficient to get the latest cursor
        # Get the latest cursor
        response = get_latest_cursor(access_token)
        if response == 404:
            return HttpResponse("Please provide a valid access token")

        cursors[user_email] = response['cursor']
        return HttpResponse(request.GET['challenge'])

    elif request.method == 'POST':

        # Get the messages of the modified files
        messages = get_updated_files(access_token, user_email)
        check_send_stream_message(user_profile, request.client,
                                  stream, topic, '\n'.join(messages))
        return json_success()
