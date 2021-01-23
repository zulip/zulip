from zerver.lib.test_classes import WebhookTestCase


class TmateHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/tmate?&api_key={api_key}&stream=test"
    FIXTURE_DIR_NAME = 'tmate'

    def test_session_register(self) -> None:
        expected_topic = "Session a1ba02fc-5684-11eb-9f1d-0242ac150002";
        expected_message = "There is a new session registered.\nConnect with: `ssh -p2222 kxEEYXAN8eQPpvWhnenxLXRmd@remotesupport.librerouter.org` or [this link](http://remotesupport.librerouter.org:4000/t/kxEEYXAN8eQPpvWhnenxLXRmd).";

        # use fixture named tmate_hello
        self.check_webhook('session_register', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")


    def test_session_close(self) -> None:
        expected_topic = "Session: a1ba02fc-5684-11eb-9f1d-0242ac150002";
        expected_message = "Session closed.";

        # use fixture named tmate_hello
        self.check_webhook('session_close', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")

    def test_session_left(self) -> None:
        expected_topic = "Session: a1ba02fc-5684-11eb-9f1d-0242ac150002";
        expected_message = "Someone with id ae4b50c0-5684-11eb-9762-0242ac150002 left.";

        # use fixture named tmate_hello
        self.check_webhook('session_left', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")

    def test_session_join(self) -> None:
        expected_topic = "Session: a1ba02fc-5684-11eb-9f1d-0242ac150002";
        expected_message = "Someone from 181.44.61.146 id ae4b50c0-5684-11eb-9762-0242ac150002 joined through web.";

        # use fixture named tmate_hello
        self.check_webhook('session_join', expected_topic, expected_message,
                           content_type="application/x-www-form-urlencoded")
