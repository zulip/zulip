# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

class PivotalV3HookTests(WebhookTestCase):
    STREAM_NAME = 'pivotal'
    URL_TEMPLATE = u"/api/v1/external/pivotal?stream={stream}&api_key={api_key}"

    def test_accepted(self) -> None:
        expected_topic = 'My new Feature story'
        expected_message = 'Leo Franchi accepted "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('accepted', expected_topic, expected_message, content_type="application/xml")

    def test_commented(self) -> None:
        expected_topic = 'Comment added'
        expected_message = 'Leo Franchi added comment: "FIX THIS NOW" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('commented', expected_topic, expected_message, content_type="application/xml")

    def test_created(self) -> None:
        expected_topic = 'My new Feature story'
        expected_message = 'Leo Franchi added "My new Feature story" \
(unscheduled feature):\n\n~~~ quote\nThis is my long description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('created', expected_topic, expected_message, content_type="application/xml")

    def test_delivered(self) -> None:
        expected_topic = 'Another new story'
        expected_message = 'Leo Franchi delivered "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('delivered', expected_topic, expected_message, content_type="application/xml")

    def test_finished(self) -> None:
        expected_topic = 'Another new story'
        expected_message = 'Leo Franchi finished "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('finished', expected_topic, expected_message, content_type="application/xml")

    def test_moved(self) -> None:
        expected_topic = 'My new Feature story'
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('moved', expected_topic, expected_message, content_type="application/xml")

    def test_rejected(self) -> None:
        expected_topic = 'Another new story'
        expected_message = 'Leo Franchi rejected "Another new story" with comments: \
"Not good enough, sorry" [(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('rejected', expected_topic, expected_message, content_type="application/xml")

    def test_started(self) -> None:
        expected_topic = 'Another new story'
        expected_message = 'Leo Franchi started "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('started', expected_topic, expected_message, content_type="application/xml")

    def test_created_estimate(self) -> None:
        expected_topic = 'Another new story'
        expected_message = 'Leo Franchi added "Another new story" \
(unscheduled feature worth 2 story points):\n\n~~~ quote\nSome loong description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)'
        self.send_and_test_stream_message('created_estimate', expected_topic, expected_message, content_type="application/xml")

    def test_type_changed(self) -> None:
        expected_topic = 'My new Feature story'
        expected_message = 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)'
        self.send_and_test_stream_message('type_changed', expected_topic, expected_message, content_type="application/xml")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data('pivotal', fixture_name, file_type='xml')

class PivotalV5HookTests(WebhookTestCase):
    STREAM_NAME = 'pivotal'
    URL_TEMPLATE = u"/api/v1/external/pivotal?stream={stream}&api_key={api_key}"

    def test_accepted(self) -> None:
        expected_topic = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **unstarted** to **accepted**"""
        self.send_and_test_stream_message('accepted', expected_topic, expected_message, content_type="application/xml")

    def test_commented(self) -> None:
        expected_topic = '#63486316: Story of the Year'
        expected_message = """Leo Franchi added a comment to [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
~~~quote
A comment on the story
~~~"""
        self.send_and_test_stream_message('commented', expected_topic, expected_message, content_type="application/xml")

    def test_created(self) -> None:
        expected_topic = '#63495662: Story that I created'
        expected_message = """Leo Franchi created bug: [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story that I created](http://www.pivotaltracker.com/story/show/63495662)
* State is **unscheduled**
* Description is

> What a description"""
        self.send_and_test_stream_message('created', expected_topic, expected_message, content_type="application/xml")

    def test_delivered(self) -> None:
        expected_topic = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **accepted** to **delivered**"""
        self.send_and_test_stream_message('delivered', expected_topic, expected_message, content_type="application/xml")

    def test_finished(self) -> None:
        expected_topic = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* state changed from **delivered** to **accepted**"""
        self.send_and_test_stream_message('finished', expected_topic, expected_message, content_type="application/xml")

    def test_moved(self) -> None:
        expected_topic = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi moved [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066) from **unstarted** to **unscheduled**"""
        self.send_and_test_stream_message('moved', expected_topic, expected_message, content_type="application/xml")

    def test_rejected(self) -> None:
        expected_topic = '#63486316: Story of the Year'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Story of the Year](http://www.pivotaltracker.com/story/show/63486316):
* Comment added:
~~~quote
Try again next time
~~~
* state changed from **delivered** to **rejected**"""
        self.send_and_test_stream_message('rejected', expected_topic, expected_message, content_type="application/xml")

    def test_started(self) -> None:
        expected_topic = '#63495972: Fresh Story'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Fresh Story](http://www.pivotaltracker.com/story/show/63495972):
* state changed from **unstarted** to **started**"""
        self.send_and_test_stream_message('started', expected_topic, expected_message, content_type="application/xml")

    def test_created_estimate(self) -> None:
        expected_topic = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate is now **3 points**"""
        self.send_and_test_stream_message('created_estimate', expected_topic, expected_message, content_type="application/xml")

    def test_type_changed(self) -> None:
        expected_topic = '#63496066: Pivotal Test'
        expected_message = """Leo Franchi updated [Hard Code](https://www.pivotaltracker.com/s/projects/807213): [Pivotal Test](http://www.pivotaltracker.com/story/show/63496066):
* estimate changed from 3 to **0 points**
* type changed from **feature** to **bug**"""
        self.send_and_test_stream_message('type_changed', expected_topic, expected_message, content_type="application/xml")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data('pivotal', "v5_{}".format(fixture_name), file_type='json')
