# -*- coding: utf-8 -*-
from six import text_type
from zerver.lib.test_helpers import WebhookTestCase

class PivotalV3HookTests(WebhookTestCase):
    STREAM_NAME = 'pivotal'
    URL_TEMPLATE = u"/api/v1/external/pivotal?stream={stream}&api_key={api_key}"

    def test_accepted(self):
        # type: () -> None
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi accepted "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('accepted', expected_subject, expected_message, content_type="application/xml")

    def test_commented(self):
        # type: () -> None
        expected_subject = 'Comment added'
        expected_message = 'Leo Franchi added comment: "FIX THIS NOW" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('commented', expected_subject, expected_message, content_type="application/xml")

    def test_created(self):
        # type: () -> None
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi added "My new Feature story" \
(unscheduled feature):\n\n~~~ quote\nThis is my long description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('created', expected_subject, expected_message, content_type="application/xml")

    def test_delivered(self):
        # type: () -> None
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi delivered "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('delivered', expected_subject, expected_message, content_type="application/xml")

    def test_finished(self):
        # type: () -> None
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi finished "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('finished', expected_subject, expected_message, content_type="application/xml")

    def test_moved(self):
        # type: () -> None
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('moved', expected_subject, expected_message, content_type="application/xml")

    def test_rejected(self):
        # type: () -> None
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi rejected "Another new story" with comments: \
"Not good enough, sorry" [(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('rejected', expected_subject, expected_message, content_type="application/xml")

    def test_started(self):
        # type: () -> None
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi started "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('started', expected_subject, expected_message, content_type="application/xml")

    def test_created_estimate(self):
        # type: () -> None
        expected_subject = 'Another new story'
        expected_message = 'Leo Franchi added "Another new story" \
(unscheduled feature worth 2 story points):\n\n~~~ quote\nSome loong description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('created_estimate', expected_subject, expected_message, content_type="application/xml")

    def test_type_changed(self):
        # type: () -> None
        expected_subject = 'My new Feature story'
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('type_changed', expected_subject, expected_message, content_type="application/xml")

    def get_body(self, fixture_name):
        # type: (text_type) -> text_type
        return self.fixture_data('pivotal', fixture_name, file_type='xml')
