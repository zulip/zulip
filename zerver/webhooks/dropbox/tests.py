# -*- coding: utf-8 -*-
from typing import Text, Any

from zerver.lib.test_classes import WebhookTestCase
from unittest.mock import patch

# FIXME : Add test cases for RENAMING/DELETING/CREATING FOLDER/FILE

GET_LATEST_CURSOR_JSON = {
    "cursor": "AAEGPVoZWonySrh1nJE-oHTkh4xBBWo5oQY1UYbekeNc5tQNtdlL6UxtP6PF1HU03R2tSfwjc9hUemdwZ-1Q3Q6DXpBnetPg3ofAXX5fc6uBARY9PfAo-7JDNND7Dvl03McXnA6hqqx-WfbDvTQDi1p2LtoLBZC0t1b-0yyMlyUR76vt5F3DwiC7VCuxQqlnOW-UgrtThbCR9s3rTzQFzbSm77GI-1XASBqHzZ_DVYoAjQ"
}
LIST_FOLDER_CONTINUE_JSON = {
    "entries": [
        {
            ".tag": "folder",
            "name": "f1",
            "path_lower": "/f1",
            "path_display": "/f1",
            "id": "id:OLvdxp2nhfAAAAAAAAAAXg"
        },
        {
            ".tag": "deleted",
            "name": "f2",
            "path_lower": "/f2",
            "path_display": "/f2"
        },
        {
            ".tag": "deleted",
            "name": "f3",
            "path_lower": "/f3",
            "path_display": "/f3"
        },
        {
            ".tag": "file",
            "name": "f4",
            "path_lower": "/f4",
            "path_display": "/f4",
            "id": "id:OLvdxp2nhfAAAAAAAAAAaQ",
            "client_modified": "2018-02-10T12:41:39Z",
            "server_modified": "2018-02-10T12:41:40Z",
            "rev": "c759d25915",
            "size": 4,
            "content_hash": "e8ee8d1fa608f11f53f6ee5462d15d944ff2680c756a0a43e5b4bf017a02081b"
        }
    ],
    "cursor": "AAEO4KHK1lc0jQdHG6AaKXnKzo4Z36Yn0m4_DXowSOhI-iiXguFJ9obzQ3EykYeW4_iUUn-ckyMuhsVVkdnoyuqG0H7CYlzevpTk0alCKzEo9n6Zi5o07SfgxRrtnVjx151lIVySbnGTr-y3r-y7UvBrqHsh1t_tbV7-pMjp6KrnIGZP6QszOCsvfxFN7bAwBKqczx0_6UW66SVd2S90xn4AkSy5uoWeQdOYn9ZTi-c6Dg",
    "has_more": False
}

ERROR_JSON = {
    "error_summary": "invalid_access_token/",
    "error": {
        ".tag": "invalid_access_token"
    }
}

def mock_requests_post_error(*args: Any, **kwargs: Any) -> Any:
    class MockResponse:
        def __init__(self, json_data: Any, status_code: int) -> None:
            self.json_data = json_data
            self.status_code = status_code

        def json(self) -> Any:
            return self.json_data
    return MockResponse(ERROR_JSON, 404)

def mock_requests_post(*args: Any, **kwargs: Any) -> Any:
    class MockResponse:
        def __init__(self, json_data: Any, status_code: int) -> None:
            self.json_data = json_data
            self.status_code = status_code

        def json(self) -> None:
            return self.json_data

    if args[0] == 'https://api.dropboxapi.com/2/files/list_folder/get_latest_cursor':
        return MockResponse(GET_LATEST_CURSOR_JSON, 200)
    elif args[0] == 'https://api.dropboxapi.com/2/files/list_folder/continue':
        return MockResponse(LIST_FOLDER_CONTINUE_JSON, 200)

class DropboxHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/dropbox?&api_key={api_key}&access_token=123465789"
    FIXTURE_DIR_NAME = 'dropbox'

    def get_body(self, fixture_name: Text) -> Text:
        return self.fixture_data("dropbox", fixture_name, file_type="json")

    def test_changes_made_but_webhook_url_not_validated(self) -> None:
        expected_subject = u"Dropbox"
        expected_message = u"Some changes were made in your dropbox account, "\
                           "verfiy your WEBHOOK URL to get detailed messages."

        with patch('requests.post', side_effect=mock_requests_post):
            self.send_and_test_stream_message('file_updated', expected_subject, expected_message,
                                              content_type="application/x-www-form-urlencoded")

    def test_verification_request(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {
            'stream_name': self.STREAM_NAME,
            'challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
            'api_key': self.test_user.api_key,
            'access_token': '123456789'
        }

        with patch('requests.post', side_effect=mock_requests_post):
            result = self.client_get(self.url, get_params)
            self.assert_in_response('9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E', result)

    def test_get_update_message(self) -> None:
        expected_subject = u"Dropbox"
        expected_message = u"ADDED Folder : /f1\nDELETED File/Folder : /f2\nDELETED File/Folder : /f3\nADDED File : /f4"

        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {
            'stream_name': self.STREAM_NAME,
            'challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
            'api_key': self.test_user.api_key,
            'access_token': '123456789'
        }

        with patch('requests.post', side_effect=mock_requests_post):
            self.client_get(self.url, get_params)  # TO GET LATEST CURSOR
            self.send_and_test_stream_message('file_updated', expected_subject, expected_message,
                                              content_type="application/x-www-form-urlencoded")

    def test_no_access_token(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {
            'stream_name': self.STREAM_NAME,
            'challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
            'api_key': self.test_user.api_key,
        }

        with patch('requests.post', side_effect=mock_requests_post):
            result = self.client_get(self.url, get_params)
            self.assert_in_response('Please append &access_token=<ACCESSTOKEN> at the end of your Webhook URL.', result)

    def test_invalid_access_token(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {
            'stream_name': self.STREAM_NAME,
            'challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
            'api_key': self.test_user.api_key,
            'access_token': '123456789'
        }

        with patch('requests.post', side_effect=mock_requests_post_error):
            result = self.client_get(self.url, get_params)
            self.assert_in_response('Please provide a valid access token', result)
