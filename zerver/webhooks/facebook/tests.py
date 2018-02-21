from typing import Optional, Text

from zerver.lib.test_classes import WebhookTestCase

class FacebookTests(WebhookTestCase):
    STREAM_NAME = 'Facebook'
    URL_TEMPLATE = "/api/v1/external/facebook?api_key={api_key}&stream={stream}&token=aaaa"
    FIXTURE_DIR_NAME = 'facebook'

    def test_application_plugin_comment(self) -> None:
        expected_subject = u'application notification'
        expected_message = u'**plugin_comment** received'\
            u'\n**Test User:**'\
            u'\n```quote'\
            u'\nTest Comment'\
            u'\n```'
        self.send_and_test_stream_message('application_plugin_comment',
                                          expected_subject, expected_message)

    def test_application_plugin_comment_reply(self) -> None:
        expected_subject = u'application notification'
        expected_message = u'**plugin_comment_reply** received'\
            u'\n**Test User 1:** (Parent)'\
            u'\n```quote'\
            u'\nTest Parent Comment'\
            u'\n```'\
            u'\n**Test User:**'\
            u'\n```quote'\
            u'\n```quote'\
            u'\nTest Comment'\
            u'\n```'\
            u'\n```'
        self.send_and_test_stream_message('application_plugin_comment_reply',
                                          expected_subject, expected_message)

    def test_page_conversations(self) -> None:
        expected_subject = u'page notification'
        expected_message = u'Updated **conversations**'\
            u'\n[Open conversations...](https://www.facebook.com/'\
            u'4444444/t_mid.14833205540:9182a4e489)'
        self.send_and_test_stream_message('page_conversations',
                                          expected_subject, expected_message)

    def test_page_website_test(self) -> None:
        expected_subject = u'page notification'
        expected_message = u'Changed **website**'
        self.send_and_test_stream_message('page_website',
                                          expected_subject, expected_message)

    def test_permissions_ads_management(self) -> None:
        expected_subject = u'permissions notification'
        expected_message = u'**ads_management permission** changed'\
            u'\n* granted'\
            u'\n  * 123123123123123'\
            u'\n  * 321321321321321'
        self.send_and_test_stream_message('permissions_ads_management',
                                          expected_subject, expected_message)

    def test_permissions_manage_pages(self) -> None:
        expected_subject = u'permissions notification'
        expected_message = u'**manage_pages permission** changed'\
            u'\n* granted'\
            u'\n  * 123123123123123'\
            u'\n  * 321321321321321'
        self.send_and_test_stream_message('permissions_manage_pages',
                                          expected_subject, expected_message)

    def test_user_email(self) -> None:
        expected_subject = u'user notification'
        expected_message = u'Changed **email**'\
            u'\nTo: *example_email@facebook.com*'
        self.send_and_test_stream_message('user_email',
                                          expected_subject, expected_message)

    def test_user_feed(self) -> None:
        expected_subject = u'user notification'
        expected_message = u'Changed **feed**'
        self.send_and_test_stream_message('user_feed',
                                          expected_subject, expected_message)

    def test_webhook_verify_request(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {'stream_name': self.STREAM_NAME,
                      'hub.challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
                      'api_key': self.test_user.api_key,
                      'hub.mode': 'subscribe',
                      'hub.verify_token': 'aaaa',
                      'token': 'aaaa'}
        result = self.client_get(self.url, get_params)
        self.assert_in_response('9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E', result)

    def test_error_webhook_verify_request_wrong_token(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {'stream_name': self.STREAM_NAME,
                      'hub.challenge': '9B2SVL4orbt5DxLMqJHI6pOTipTqingt2YFMIO0g06E',
                      'api_key': self.test_user.api_key,
                      'hub.mode': 'subscribe',
                      'hub.verify_token': 'aaaa',
                      'token': 'wrong_token'}
        result = self.client_get(self.url, get_params)
        self.assert_in_response('Error: Token is wrong', result)

    def test_error_webhook_verify_request_unsupported_method(self) -> None:
        self.subscribe(self.test_user, self.STREAM_NAME)
        get_params = {'stream_name': self.STREAM_NAME,
                      'api_key': self.test_user.api_key,
                      'hub.mode': 'unsupported_method',
                      'token': 'aaaa'}
        result = self.client_get(self.url, get_params)
        self.assert_in_response('Error: Unsupported method', result)
