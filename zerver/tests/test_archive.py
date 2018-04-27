# -*- coding: utf-8 -*-
from django.http import HttpResponse
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.actions import do_change_stream_web_public

class GlobalPublicStreamTest(ZulipTestCase):

    def test_non_existant_stream_id(self) -> None:
        # Here we use a relatively big number as stream id assumming such an id
        # won't exist in the test DB.
        result = self.client_get("/archive/streams/100000000/topic/TopicGlobal")
        self.assert_json_error(result, 'Invalid stream id')

    def test_non_web_public_stream(self) -> None:
        test_stream = self.make_stream('Test Public Archives')
        result = self.client_get(
            "/archive/streams/" + str(test_stream.id) + "/topic/notpublicglobalstream"
        )
        self.assert_in_success_response(["This stream does not exist."], result)

    def test_non_existant_topic(self) -> None:
        test_stream = self.make_stream('Test Public Archives')
        do_change_stream_web_public(test_stream, True)
        result = self.client_get(
            "/archive/streams/" + str(test_stream.id) + "/topic/nonexistenttopic"
        )
        self.assert_in_success_response(["This topic does not exist."], result)

    def test_web_public_stream_topic(self) -> None:
        test_stream = self.make_stream('Test Public Archives')
        do_change_stream_web_public(test_stream, True)

        def send_msg_and_get_result(msg: str) -> HttpResponse:
            self.send_stream_message(
                self.example_email("iago"),
                "Test Public Archives",
                msg,
                'TopicGlobal'
            )
            return self.client_get(
                "/archive/streams/" + str(test_stream.id) + "/topic/TopicGlobal"
            )

        result = send_msg_and_get_result('Test Message 1')
        self.assert_in_success_response(["Test Message 1"], result)
        result = send_msg_and_get_result('/me goes testing.')
        self.assert_in_success_response(["goes testing."], result)
