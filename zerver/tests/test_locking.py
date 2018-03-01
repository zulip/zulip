
import ujson

from django.http import HttpResponse
from mock import patch

from zerver.lib.test_classes import ZulipTestCase

from zerver.models import (
    get_stream,
    UserProfile,
)

from zerver.lib.locked_topics import (
    add_locked_topic,
    get_locked_topics,
    topic_is_locked
)

class LockedTopicsTests(ZulipTestCase):
    def test_add_locked_topic(self) -> None:
        user = self.example_user('iago')
        email = user.email
        self.login(email)
        stream = get_stream(u'Verona', user.realm)
        url = '/api/v1/lock_topic'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)

        self.assert_json_success(result)
        self.assertIn([u'Verona', u'Verona3'], get_locked_topics())
        self.assertTrue(topic_is_locked(stream.id, 'Verona3'))

    def test_remove_locked_topic(self) -> None:
        user = self.example_user('iago')
        email = user.email
        self.login(email)
        stream = get_stream(u'Verona', user.realm)
        add_locked_topic(stream.id, u'Verona3')

        url = '/api/v1/lock_topic'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)

        self.assert_json_success(result)
        self.assertNotIn([u'Verona', u'Verona3'], get_locked_topics())
        self.assertFalse(topic_is_locked(stream.id, 'Verona3'))

    def test_add_locked_topic_no_admin(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)
        url = '/api/v1/lock_topic'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_remove_locked_topic_no_admin(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)
        url = '/api/v1/lock_topic'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_locked_topic_add_invalid(self) -> None:
        user = self.example_user('iago')
        email = user.email
        self.login(email)

        realm = user.realm
        stream = get_stream(u'Verona', realm)
        add_locked_topic(stream.id, u'Verona3')

        url = '/api/v1/lock_topic'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic already locked")

    def test_locked_topic_remove_invalid(self) -> None:
        user = self.example_user('iago')
        email = user.email
        self.login(email)

        url = '/api/v1/lock_topic'
        data = {'stream': 'BOGUS', 'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Invalid stream name 'BOGUS'")

        data = {'stream': 'Verona', 'topic': 'BOGUS', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not there in the locked_topics list")

        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not there in the locked_topics list")
