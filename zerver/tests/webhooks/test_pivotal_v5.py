# -*- coding: utf-8 -*-
from six import text_type
from zerver.lib.test_helpers import WebhookTestCase

class PivotalV5HookTests(WebhookTestCase):
    STREAM_NAME = 'pivotal'
    URL_TEMPLATE = u"/api/v1/external/pivotal?stream={stream}&api_key={api_key}"

    def test_accepted(self):
        # type: () -> None
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **unstarted** to **accepted**
"""
        self.send_and_test_stream_message('accepted', expected_subject, expected_message, content_type="application/xml")

    def test_commented(self):
        # type: () -> None
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi added a comment to [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
~~~quote
A comment on the story
~~~"""
        self.send_and_test_stream_message('commented', expected_subject, expected_message, content_type="application/xml")

    def test_created(self):
        # type: () -> None
        expected_subject = '#63495662: Story that I created'
        expected_message = """Leo Franchi created bug: [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story that I created](http://www.pivotaltracker.com/story/show/63495662)
* State is **unscheduled**
* Description is

> What a description"""
        self.send_and_test_stream_message('created', expected_subject, expected_message, content_type="application/xml")

    def test_delivered(self):
        # type: () -> None
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **accepted** to **delivered**
"""
        self.send_and_test_stream_message('delivered', expected_subject, expected_message, content_type="application/xml")

    def test_finished(self):
        # type: () -> None
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **delivered** to **accepted**
"""
        self.send_and_test_stream_message('finished', expected_subject, expected_message, content_type="application/xml")

    def test_moved(self):
        # type: () -> None
        expected_subject = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi moved [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066) from **unstarted** to **unscheduled**"""
        self.send_and_test_stream_message('moved', expected_subject, expected_message, content_type="application/xml")

    def test_rejected(self):
        # type: () -> None
        expected_subject = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* Comment added:
~~~quote
Try again next time
~~~
* state changed from **delivered** to **rejected**
"""
        self.send_and_test_stream_message('rejected', expected_subject, expected_message, content_type="application/xml")

    def test_started(self):
        # type: () -> None
        expected_subject = '#63495972: Fresh Story'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Fresh Story](http://www.pivotaltracker.com/story/show/63495972):
* state changed from **unstarted** to **started**
"""
        self.send_and_test_stream_message('started', expected_subject, expected_message, content_type="application/xml")

    def test_created_estimate(self):
        # type: () -> None
        expected_subject = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate is now **3 points**
"""
        self.send_and_test_stream_message('created_estimate', expected_subject, expected_message, content_type="application/xml")

    def test_type_changed(self):
        # type: () -> None
        expected_subject = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate changed from 3 to **0 points**
* type changed from **feature** to **bug**
"""
        self.send_and_test_stream_message('type_changed', expected_subject, expected_message, content_type="application/xml")

    def get_body(self, fixture_name):
        # type: (text_type) -> text_type
        return self.fixture_data('pivotal', "v5_{}".format(fixture_name), file_type='json')
