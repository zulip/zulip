# -*- coding: utf-8 -*-
from __future__ import absolute_import

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Text

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now

from zerver.lib import cache

from zerver.lib.test_helpers import (
    get_subscription, queries_captured, tornado_redirected_to_list
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.decorator import (
    JsonableError
)

from zerver.lib.response import (
    json_error,
    json_success,
)

from zerver.lib.streams import (
    access_stream_by_id, access_stream_by_name
)

from zerver.lib.test_runner import (
    slow
)

from zerver.models import (
    get_display_recipient, Message, Realm, Recipient, Stream, Subscription,
    DefaultStream, UserProfile, get_user_profile_by_id, active_user_ids,
)

from zerver.lib.actions import (
    do_add_default_stream, do_change_is_admin, do_set_realm_property,
    do_create_realm, do_remove_default_stream,
    gather_subscriptions_helper, bulk_add_subscriptions, bulk_remove_subscriptions,
    gather_subscriptions, get_default_streams_for_realm, get_realm, get_stream,
    get_user, set_default_streams, check_stream_name,
    create_stream_if_needed, create_streams_if_needed,
    do_deactivate_stream,
    stream_welcome_message,
)

from zerver.views.streams import (
    compose_views
)

from django.http import HttpResponse
import mock
import random
import ujson
import six
from six.moves import range, urllib, zip

class TestCreateStreams(ZulipTestCase):
    def test_creating_streams(self):
        # type: () -> None
        stream_names = [u'new1', u'new2', u'new3']
        stream_descriptions = [u'des1', u'des2', u'des3']
        realm = get_realm('zulip')

        new_streams, existing_streams = create_streams_if_needed(
            realm,
            [{"name": stream_name,
              "description": stream_description,
              "invite_only": True}
             for (stream_name, stream_description) in zip(stream_names, stream_descriptions)])

        self.assertEqual(len(new_streams), 3)
        self.assertEqual(len(existing_streams), 0)

        actual_stream_names = {stream.name for stream in new_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in new_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in new_streams:
            self.assertTrue(stream.invite_only)

        new_streams, existing_streams = create_streams_if_needed(
            realm,
            [{"name": stream_name,
              "description": stream_description,
              "invite_only": True}
             for (stream_name, stream_description) in zip(stream_names, stream_descriptions)])

        self.assertEqual(len(new_streams), 0)
        self.assertEqual(len(existing_streams), 3)

        actual_stream_names = {stream.name for stream in existing_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in existing_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in existing_streams:
            self.assertTrue(stream.invite_only)

    def test_welcome_message(self):
        # type: () -> None
        realm = get_realm('zulip')
        name = u'New Stream'

        new_stream, _ = create_stream_if_needed(
            realm=realm,
            stream_name=name
        )
        welcome_message = stream_welcome_message(new_stream)

        self.assertEqual(
            welcome_message,
            u'Welcome to #**New Stream**.'
        )

        new_stream.description = 'Talk about **stuff**.'

        welcome_message = stream_welcome_message(new_stream)

        self.assertEqual(
            welcome_message,
            'Welcome to #**New Stream**.'
            '\n\n'
            '**Description**: Talk about **stuff**.'
        )

class RecipientTest(ZulipTestCase):
    def test_recipient(self):
        # type: () -> None
        realm = get_realm('zulip')
        stream = get_stream('Verona', realm)
        recipient = Recipient.objects.get(
            type_id=stream.id,
            type=Recipient.STREAM,
        )
        self.assertEqual(str(recipient), '<Recipient: Verona (%d, %d)>' % (
            stream.id, Recipient.STREAM))

class StreamAdminTest(ZulipTestCase):
    def test_make_stream_public(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        self.make_stream('private_stream', invite_only=True)

        do_change_is_admin(user_profile, True)
        params = {
            'stream_name': ujson.dumps('private_stream'),
            'is_private': ujson.dumps(False)
        }
        stream_id = get_stream('private_stream', user_profile.realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_error(result, 'Invalid stream id')

        self.subscribe(user_profile, 'private_stream')

        do_change_is_admin(user_profile, True)
        params = {
            'stream_name': ujson.dumps('private_stream'),
            'is_private': ujson.dumps(False)
        }
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_success(result)

        realm = user_profile.realm
        stream = get_stream('private_stream', realm)
        self.assertFalse(stream.invite_only)

    def test_make_stream_private(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        realm = user_profile.realm
        self.make_stream('public_stream', realm=realm)

        do_change_is_admin(user_profile, True)
        params = {
            'stream_name': ujson.dumps('public_stream'),
            'is_private': ujson.dumps(True)
        }
        stream_id = get_stream('public_stream', realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_success(result)
        stream = get_stream('public_stream', realm)
        self.assertTrue(stream.invite_only)

    def test_deactivate_stream_backend(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        stream = self.make_stream('new_stream')
        self.subscribe(user_profile, stream.name)
        do_change_is_admin(user_profile, True)

        result = self.client_delete('/json/streams/%d' % (stream.id,))
        self.assert_json_success(result)
        subscription_exists = Subscription.objects.filter(
            user_profile=user_profile,
            recipient__type_id=stream.id,
            recipient__type=Recipient.STREAM,
            active=True,
        ).exists()
        self.assertFalse(subscription_exists)

    def test_deactivate_stream_removes_default_stream(self):
        # type: () -> None
        stream = self.make_stream('new_stream')
        do_add_default_stream(stream)
        self.assertEqual(1, DefaultStream.objects.filter(stream=stream).count())
        do_deactivate_stream(stream)
        self.assertEqual(0, DefaultStream.objects.filter(stream=stream).count())

    def test_vacate_private_stream_removes_default_stream(self):
        # type: () -> None
        stream = self.make_stream('new_stream', invite_only=True)
        self.subscribe(self.example_user("hamlet"), stream.name)
        do_add_default_stream(stream)
        self.assertEqual(1, DefaultStream.objects.filter(stream=stream).count())
        self.unsubscribe(self.example_user("hamlet"), stream.name)
        self.assertEqual(0, DefaultStream.objects.filter(stream=stream).count())
        # Fetch stream again from database.
        stream = Stream.objects.get(id=stream.id)
        self.assertTrue(stream.deactivated)

    def test_deactivate_stream_backend_requires_existing_stream(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        self.make_stream('new_stream')
        do_change_is_admin(user_profile, True)

        result = self.client_delete('/json/streams/999999999')
        self.assert_json_error(result, u'Invalid stream id')

    def test_deactivate_stream_backend_requires_realm_admin(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        self.subscribe(user_profile, 'new_stream')

        stream_id = get_stream('new_stream', user_profile.realm).id
        result = self.client_delete('/json/streams/%d' % (stream_id,))
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_private_stream_live_updates(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)

        do_change_is_admin(user_profile, True)

        self.make_stream('private_stream', invite_only=True)
        self.subscribe(user_profile, 'private_stream')
        self.subscribe(self.example_user("cordelia"), 'private_stream')

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            stream_id = get_stream('private_stream', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'description': ujson.dumps('Test description')})
        self.assert_json_success(result)
        # Should be just a description change event
        self.assert_length(events, 1)

        cordelia = self.example_user('cordelia')
        prospero = self.example_user('prospero')

        notified_user_ids = set(events[-1]['users'])
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(cordelia.id, notified_user_ids)
        self.assertNotIn(prospero.id, notified_user_ids)

        events = []
        with tornado_redirected_to_list(events):
            stream_id = get_stream('private_stream', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('whatever')})
        self.assert_json_success(result)
        # Should be a name event and an email address event
        self.assert_length(events, 2)

        notified_user_ids = set(events[-1]['users'])
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(cordelia.id, notified_user_ids)
        self.assertNotIn(prospero.id, notified_user_ids)

    def test_rename_stream(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        realm = user_profile.realm
        stream = self.subscribe(user_profile, 'stream_name1')
        do_change_is_admin(user_profile, True)

        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('stream_name1')})
        self.assert_json_error(result, "Stream already has that name!")
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('Denmark')})
        self.assert_json_error(result, "Stream name 'Denmark' is already taken")
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('denmark ')})
        self.assert_json_error(result, "Stream name 'denmark' is already taken")

        # Do a rename that is case-only--this should succeed.
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('sTREAm_name1')})
        self.assert_json_success(result)

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            stream_id = get_stream('stream_name1', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('stream_name2')})
        self.assert_json_success(result)

        event = events[1]['event']
        self.assertEqual(event, dict(
            op='update',
            type='stream',
            property='name',
            value='stream_name2',
            stream_id=stream_id,
            name='sTREAm_name1'
        ))
        notified_user_ids = set(events[1]['users'])

        self.assertRaises(Stream.DoesNotExist, get_stream, 'stream_name1', realm)

        stream_name2_exists = get_stream('stream_name2', realm)
        self.assertTrue(stream_name2_exists)

        self.assertEqual(notified_user_ids, set(active_user_ids(realm.id)))
        self.assertIn(user_profile.id,
                      notified_user_ids)
        self.assertIn(self.example_user('prospero').id,
                      notified_user_ids)

        # Test case to handle unicode stream name change
        # *NOTE: Here Encoding is needed when Unicode string is passed as an argument*
        with tornado_redirected_to_list(events):
            stream_id = stream_name2_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps(u'नया नाम'.encode('utf-8'))})
        self.assert_json_success(result)
        # While querying, system can handle unicode strings.
        stream_name_uni_exists = get_stream(u'नया नाम', realm)
        self.assertTrue(stream_name_uni_exists)

        # Test case to handle changing of unicode stream name to newer name
        # NOTE: Unicode string being part of URL is handled cleanly
        # by client_patch call, encoding of URL is not needed.
        with tornado_redirected_to_list(events):
            stream_id = stream_name_uni_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps(u'नाम में क्या रक्खा हे'.encode('utf-8'))})
        self.assert_json_success(result)
        # While querying, system can handle unicode strings.
        self.assertRaises(Stream.DoesNotExist, get_stream, u'नया नाम', realm)

        stream_name_new_uni_exists = get_stream(u'नाम में क्या रक्खा हे', realm)
        self.assertTrue(stream_name_new_uni_exists)

        # Test case to change name from one language to other.
        with tornado_redirected_to_list(events):
            stream_id = stream_name_new_uni_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps(u'français'.encode('utf-8'))})
        self.assert_json_success(result)
        stream_name_fr_exists = get_stream(u'français', realm)
        self.assertTrue(stream_name_fr_exists)

        # Test case to change name to mixed language name.
        with tornado_redirected_to_list(events):
            stream_id = stream_name_fr_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps(u'français name'.encode('utf-8'))})
        self.assert_json_success(result)
        stream_name_mixed_exists = get_stream(u'français name', realm)
        self.assertTrue(stream_name_mixed_exists)

    def test_rename_stream_requires_realm_admin(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        self.make_stream('stream_name1')

        stream_id = get_stream('stream_name1', user_profile.realm).id
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'new_name': ujson.dumps('stream_name2')})
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_change_stream_description(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        realm = user_profile.realm
        self.subscribe(user_profile, 'stream_name1')
        do_change_is_admin(user_profile, True)

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            stream_id = get_stream('stream_name1', realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'description': ujson.dumps('Test description')})
        self.assert_json_success(result)

        event = events[0]['event']
        self.assertEqual(event, dict(
            op='update',
            type='stream',
            property='description',
            value='Test description',
            stream_id=stream_id,
            name='stream_name1'
        ))
        notified_user_ids = set(events[0]['users'])

        stream = get_stream('stream_name1', realm)
        self.assertEqual(notified_user_ids, set(active_user_ids(realm.id)))
        self.assertIn(user_profile.id,
                      notified_user_ids)
        self.assertIn(self.example_user('prospero').id,
                      notified_user_ids)

        self.assertEqual('Test description', stream.description)

    def test_change_stream_description_requires_realm_admin(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)

        self.subscribe(user_profile, 'stream_name1')
        do_change_is_admin(user_profile, False)

        stream_id = get_stream('stream_name1', user_profile.realm).id
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'description': ujson.dumps('Test description')})
        self.assert_json_error(result, 'Must be a realm administrator')

    def set_up_stream_for_deletion(self, stream_name, invite_only=False,
                                   subscribed=True):
        # type: (str, bool, bool) -> Stream
        """
        Create a stream for deletion by an administrator.
        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        stream = self.make_stream(stream_name, invite_only=invite_only)

        # For testing deleting streams you aren't on.
        if subscribed:
            self.subscribe(user_profile, stream_name)

        do_change_is_admin(user_profile, True)

        return stream

    def delete_stream(self, stream):
        # type: (Stream) -> None
        """
        Delete the stream and assess the result.
        """
        active_name = stream.name
        realm = stream.realm
        stream_id = stream.id

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_delete('/json/streams/' + str(stream_id))
        self.assert_json_success(result)

        # We no longer send subscription events for stream deactivations.
        sub_events = [e for e in events if e['event']['type'] == 'subscription']
        self.assertEqual(sub_events, [])

        stream_events = [e for e in events if e['event']['type'] == 'stream']
        self.assertEqual(len(stream_events), 1)
        event = stream_events[0]['event']
        self.assertEqual(event['op'], 'delete')
        self.assertEqual(event['streams'][0]['stream_id'], stream.id)

        with self.assertRaises(Stream.DoesNotExist):
            Stream.objects.get(realm=get_realm("zulip"), name=active_name)

        # A deleted stream's name is changed, is deactivated, is invite-only,
        # and has no subscribers.
        deactivated_stream_name = "!DEACTIVATED:" + active_name
        deactivated_stream = get_stream(deactivated_stream_name, realm)
        self.assertTrue(deactivated_stream.deactivated)
        self.assertTrue(deactivated_stream.invite_only)
        self.assertEqual(deactivated_stream.name, deactivated_stream_name)
        subscribers = self.users_subscribed_to_stream(
            deactivated_stream_name, realm)
        self.assertEqual(subscribers, [])

        # It doesn't show up in the list of public streams anymore.
        result = self.client_get("/json/streams?include_subscribed=false")
        public_streams = [s["name"] for s in result.json()["streams"]]
        self.assertNotIn(active_name, public_streams)
        self.assertNotIn(deactivated_stream_name, public_streams)

        # Even if you could guess the new name, you can't subscribe to it.
        result = self.client_post(
            "/json/users/me/subscriptions",
            {"subscriptions": ujson.dumps([{"name": deactivated_stream_name}])})
        self.assert_json_error(
            result, "Unable to access stream (%s)." % (deactivated_stream_name,))

    def test_you_must_be_realm_admin(self):
        # type: () -> None
        """
        You must be on the realm to create a stream.
        """
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)

        other_realm = Realm.objects.create(string_id='other')
        stream = self.make_stream('other_realm_stream', realm=other_realm)

        result = self.client_delete('/json/streams/' + str(stream.id))
        self.assert_json_error(result, 'Must be a realm administrator')

        # Even becoming a realm admin doesn't help us for an out-of-realm
        # stream.
        do_change_is_admin(user_profile, True)
        result = self.client_delete('/json/streams/' + str(stream.id))
        self.assert_json_error(result, 'Invalid stream id')

    def test_delete_public_stream(self):
        # type: () -> None
        """
        When an administrator deletes a public stream, that stream is not
        visible to users at all anymore.
        """
        stream = self.set_up_stream_for_deletion("newstream")
        self.delete_stream(stream)

    def test_delete_private_stream(self):
        # type: () -> None
        """
        Administrators can delete private streams they are on.
        """
        stream = self.set_up_stream_for_deletion("newstream", invite_only=True)
        self.delete_stream(stream)

    def test_delete_streams_youre_not_on(self):
        # type: () -> None
        """
        Administrators can delete public streams they aren't on, including
        private streams in their realm.
        """
        pub_stream = self.set_up_stream_for_deletion(
            "pubstream", subscribed=False)
        self.delete_stream(pub_stream)

        priv_stream = self.set_up_stream_for_deletion(
            "privstream", subscribed=False, invite_only=True)
        self.delete_stream(priv_stream)

    def attempt_unsubscribe_of_principal(self, is_admin=False, is_subbed=True,
                                         invite_only=False, other_user_subbed=True):
        # type: (bool, bool, bool, bool) -> HttpResponse

        # Set up the main user, who is in most cases an admin.
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        if is_admin:
            do_change_is_admin(user_profile, True)

        # Set up the stream.
        stream_name = u"hümbüǵ"
        self.make_stream(stream_name, invite_only=invite_only)

        # Set up the principal to be unsubscribed.
        other_user_profile = self.example_user('cordelia')
        other_email = other_user_profile.email

        # Subscribe the admin and/or principal as specified in the flags.
        if is_subbed:
            self.subscribe(user_profile, stream_name)
        if other_user_subbed:
            self.subscribe(other_user_profile, stream_name)

        result = self.client_delete(
            "/json/users/me/subscriptions",
            {"subscriptions": ujson.dumps([stream_name]),
             "principals": ujson.dumps([other_email])})

        # If the removal succeeded, then assert that Cordelia is no longer subscribed.
        if result.status_code not in [400]:
            subbed_users = self.users_subscribed_to_stream(stream_name, other_user_profile.realm)
            self.assertNotIn(other_user_profile, subbed_users)

        return result

    def test_cant_remove_others_from_stream(self):
        # type: () -> None
        """
        If you're not an admin, you can't remove other people from streams.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=False, is_subbed=True, invite_only=False,
            other_user_subbed=True)
        self.assert_json_error(
            result, "This action requires administrative rights")

    def test_admin_remove_others_from_public_stream(self):
        # type: () -> None
        """
        If you're an admin, you can remove people from public streams, even
        those you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=True, is_subbed=True, invite_only=False,
            other_user_subbed=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 1)
        self.assertEqual(len(json["not_subscribed"]), 0)

    def test_admin_remove_others_from_subbed_private_stream(self):
        # type: () -> None
        """
        If you're an admin, you can remove other people from private streams you
        are on.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=True, is_subbed=True, invite_only=True,
            other_user_subbed=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 1)
        self.assertEqual(len(json["not_subscribed"]), 0)

    def test_admin_remove_others_from_unsubbed_private_stream(self):
        # type: () -> None
        """
        Even if you're an admin, you can't remove people from private
        streams you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=True, is_subbed=False, invite_only=True,
            other_user_subbed=True)
        self.assert_json_error(result, "Cannot administer invite-only streams this way")

    def test_create_stream_by_admins_only_setting(self):
        # type: () -> None
        """
        When realm.create_stream_by_admins_only setting is active and
        the number of days since the user had joined is less than waiting period
        threshold, non admin users shouldn't be able to create new streams.
        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        do_set_realm_property(user_profile.realm, 'create_stream_by_admins_only', True)

        stream_name = ['adminsonlysetting']
        result = self.common_subscribe_to_streams(
            email,
            stream_name
        )
        self.assert_json_error(result, 'User cannot create streams.')

    def test_create_stream_by_waiting_period_threshold(self):
        # type: () -> None
        """
        Non admin users with account age greater or equal to waiting period
        threshold should be able to create new streams.
        """
        user_profile = self.example_user('hamlet')
        user_profile.date_joined = timezone_now()
        user_profile.save()
        email = user_profile.email
        self.login(email)
        do_change_is_admin(user_profile, False)

        do_set_realm_property(user_profile.realm, 'waiting_period_threshold', 10)

        stream_name = ['waitingperiodtest']
        result = self.common_subscribe_to_streams(
            email,
            stream_name
        )
        self.assert_json_error(result, 'User cannot create streams.')

        do_set_realm_property(user_profile.realm, 'waiting_period_threshold', 0)

        result = self.common_subscribe_to_streams(
            email,
            stream_name
        )
        self.assert_json_success(result)

    def test_remove_already_not_subbed(self):
        # type: () -> None
        """
        Trying to unsubscribe someone who already isn't subscribed to a stream
        fails gracefully.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=True, is_subbed=False, invite_only=False,
            other_user_subbed=False)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 0)
        self.assertEqual(len(json["not_subscribed"]), 1)

    def test_remove_invalid_user(self):
        # type: () -> None
        """
        Trying to unsubscribe an invalid user from a stream fails gracefully.
        """
        user_profile = self.example_user('hamlet')
        admin_email = user_profile.email
        self.login(admin_email)
        do_change_is_admin(user_profile, True)

        stream_name = u"hümbüǵ"
        self.make_stream(stream_name)

        result = self.client_delete("/json/users/me/subscriptions",
                                    {"subscriptions": ujson.dumps([stream_name]),
                                     "principals": ujson.dumps(["baduser@zulip.com"])})
        self.assert_json_error(
            result,
            "User not authorized to execute queries on behalf of 'baduser@zulip.com'",
            status_code=403)

class DefaultStreamTest(ZulipTestCase):
    def get_default_stream_names(self, realm):
        # type: (Realm) -> Set[Text]
        streams = get_default_streams_for_realm(realm.id)
        stream_names = [s.name for s in streams]
        return set(stream_names)

    def get_default_stream_descriptions(self, realm):
        # type: (Realm) -> Set[Text]
        streams = get_default_streams_for_realm(realm.id)
        stream_descriptions = [s.description for s in streams]
        return set(stream_descriptions)

    def test_set_default_streams(self):
        # type: () -> None
        realm = do_create_realm("testrealm", "Test Realm")
        stream_dict = {
            "apple": {"description": "A red fruit", "invite_only": False},
            "banana": {"description": "A yellow fruit", "invite_only": False},
            "Carrot Cake": {"description": "A delicious treat", "invite_only": False}
        }  # type: Dict[Text, Dict[Text, Any]]
        expected_names = list(stream_dict.keys())
        expected_names.append("announce")
        expected_descriptions = [i["description"] for i in stream_dict.values()] + [""]
        set_default_streams(realm, stream_dict)
        stream_names_set = self.get_default_stream_names(realm)
        stream_descriptions_set = self.get_default_stream_descriptions(realm)
        self.assertEqual(stream_names_set, set(expected_names))
        self.assertEqual(stream_descriptions_set, set(expected_descriptions))

    def test_set_default_streams_no_notifications_stream(self):
        # type: () -> None
        realm = do_create_realm("testrealm", "Test Realm")
        realm.notifications_stream = None
        realm.save(update_fields=["notifications_stream"])
        stream_dict = {
            "apple": {"description": "A red fruit", "invite_only": False},
            "banana": {"description": "A yellow fruit", "invite_only": False},
            "Carrot Cake": {"description": "A delicious treat", "invite_only": False}
        }  # type: Dict[Text, Dict[Text, Any]]
        expected_names = list(stream_dict.keys())
        expected_descriptions = [i["description"] for i in stream_dict.values()]
        set_default_streams(realm, stream_dict)
        stream_names_set = self.get_default_stream_names(realm)
        stream_descriptions_set = self.get_default_stream_descriptions(realm)
        self.assertEqual(stream_names_set, set(expected_names))
        self.assertEqual(stream_descriptions_set, set(expected_descriptions))

    def test_add_and_remove_default_stream(self):
        # type: () -> None
        realm = get_realm("zulip")
        (stream, _) = create_stream_if_needed(realm, "Added Stream")
        orig_stream_names = self.get_default_stream_names(realm)
        do_add_default_stream(stream)
        new_stream_names = self.get_default_stream_names(realm)
        added_stream_names = new_stream_names - orig_stream_names
        self.assertEqual(added_stream_names, set(['Added Stream']))
        # idempotentcy--2nd call to add_default_stream should be a noop
        do_add_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), new_stream_names)

        # start removing
        do_remove_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)
        # idempotentcy--2nd call to remove_default_stream should be a noop
        do_remove_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)

    def test_api_calls(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        do_change_is_admin(user_profile, True)
        stream_name = 'stream ADDED via api'
        (stream, _) = create_stream_if_needed(user_profile.realm, stream_name)
        result = self.client_post('/json/default_streams', dict(stream_name=stream_name))
        self.assert_json_success(result)
        self.assertTrue(stream_name in self.get_default_stream_names(user_profile.realm))

        # and remove it
        result = self.client_delete('/json/default_streams', dict(stream_name=stream_name))
        self.assert_json_success(result)
        self.assertFalse(stream_name in self.get_default_stream_names(user_profile.realm))

class SubscriptionPropertiesTest(ZulipTestCase):
    def test_set_stream_color(self):
        # type: () -> None
        """
        A POST request to /api/v1/users/me/subscriptions/properties with stream_id and
        color data sets the stream color, and for that stream only.
        """
        test_user = self.example_user('hamlet')
        test_email = test_user.email
        test_realm = test_user.realm
        self.login(test_email)

        old_subs, _ = gather_subscriptions(test_user)
        sub = old_subs[0]
        stream_id = sub['stream_id']
        new_color = "#ffffff"  # TODO: ensure that this is different from old_color
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "stream_id": stream_id,
                                                "value": "#ffffff"}])},
            **self.api_auth(test_email))

        self.assert_json_success(result)

        new_subs = gather_subscriptions(get_user(test_email, test_realm))[0]
        found_sub = None
        for sub in new_subs:
            if sub['stream_id'] == stream_id:
                found_sub = sub
                break

        assert(found_sub is not None)
        self.assertEqual(found_sub['color'], new_color)

        new_subs.remove(found_sub)
        for sub in old_subs:
            if sub['stream_id'] == stream_id:
                found_sub = sub
                break
        old_subs.remove(found_sub)
        self.assertEqual(old_subs, new_subs)

    def test_set_color_missing_stream_id(self):
        # type: () -> None
        """
        Updating the color property requires a `stream_id` key.
        """
        test_user = self.example_user('hamlet')
        test_email = test_user.email
        self.login(test_email)
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "value": "#ffffff"}])},
            **self.api_auth(test_email))

        self.assert_json_error(
            result, "stream_id key is missing from subscription_data[0]")

    def test_set_color_unsubscribed_stream_id(self):
        # type: () -> None
        """
        Updating the color property requires a subscribed stream.
        """
        test_email = self.example_email("hamlet")
        self.login(test_email)
        test_realm = get_realm("zulip")

        subscribed, unsubscribed, never_subscribed = gather_subscriptions_helper(
            get_user(test_email, test_realm))
        not_subbed = unsubscribed + never_subscribed
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "stream_id": not_subbed[0]["stream_id"],
                                                "value": "#ffffff"}])},
            **self.api_auth(test_email))
        self.assert_json_error(
            result, "Not subscribed to stream id %d" % (not_subbed[0]["stream_id"],))

    def test_set_color_missing_color(self):
        # type: () -> None
        """
        Updating the color property requires a color.
        """
        test_user = self.example_user('hamlet')
        test_email = test_user.email
        self.login(test_email)
        subs = gather_subscriptions(test_user)[0]
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(
            result, "value key is missing from subscription_data[0]")

    def test_set_pin_to_top(self):
        # type: () -> None
        """
        A POST request to /api/v1/users/me/subscriptions/properties with stream_id and
        pin_to_top data pins the stream.
        """
        user_profile = self.example_user('hamlet')
        test_email = user_profile.email
        self.login(test_email)

        old_subs, _ = gather_subscriptions(user_profile)
        sub = old_subs[0]
        stream_id = sub['stream_id']
        new_pin_to_top = not sub['pin_to_top']
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "pin_to_top",
                                                "stream_id": stream_id,
                                                "value": new_pin_to_top}])},
            **self.api_auth(test_email))

        self.assert_json_success(result)

        updated_sub = get_subscription(sub['name'], user_profile)

        self.assertIsNotNone(updated_sub)
        self.assertEqual(updated_sub.pin_to_top, new_pin_to_top)

    def test_set_subscription_property_incorrect(self):
        # type: () -> None
        """
        Trying to set a property incorrectly returns a JSON error.
        """
        test_user = self.example_user('hamlet')
        test_email = test_user.email
        self.login(test_email)
        subs = gather_subscriptions(test_user)[0]

        property_name = "in_home_view"
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": property_name,
                                                "value": "bad",
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(result,
                               '%s is not a boolean' % (property_name,))

        property_name = "desktop_notifications"
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": property_name,
                                                "value": "bad",
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(result,
                               '%s is not a boolean' % (property_name,))

        property_name = "audible_notifications"
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": property_name,
                                                "value": "bad",
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(result,
                               '%s is not a boolean' % (property_name,))

        property_name = "push_notifications"
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": property_name,
                                                "value": "bad",
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(result,
                               '%s is not a boolean' % (property_name,))

        property_name = "color"
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": property_name,
                                                "value": False,
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(result,
                               '%s is not a string' % (property_name,))

    def test_json_subscription_property_invalid_stream(self):
        # type: () -> None
        test_email = self.example_email("hamlet")
        self.login(test_email)

        stream_id = 1000
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "in_home_view",
                                                "stream_id": stream_id,
                                                "value": False}])},
            **self.api_auth(test_email))
        self.assert_json_error(result, "Invalid stream id")

    def test_set_invalid_property(self):
        # type: () -> None
        """
        Trying to set an invalid property returns a JSON error.
        """
        test_user = self.example_user('hamlet')
        test_email = test_user.email
        self.login(test_email)
        subs = gather_subscriptions(test_user)[0]
        result = self.client_post(
            "/api/v1/users/me/subscriptions/properties",
            {"subscription_data": ujson.dumps([{"property": "bad",
                                                "value": "bad",
                                                "stream_id": subs[0]["stream_id"]}])},
            **self.api_auth(test_email))

        self.assert_json_error(result,
                               "Unknown subscription property: bad")

class SubscriptionRestApiTest(ZulipTestCase):
    def test_basic_add_delete(self):
        # type: () -> None
        email = self.example_email('hamlet')
        realm = self.example_user('hamlet').realm
        self.login(email)

        # add
        request = {
            'add': ujson.dumps([{'name': 'my_test_stream_1'}])
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_success(result)
        streams = self.get_streams(email, realm)
        self.assertTrue('my_test_stream_1' in streams)

        # now delete the same stream
        request = {
            'delete': ujson.dumps(['my_test_stream_1'])
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_success(result)
        streams = self.get_streams(email, realm)
        self.assertTrue('my_test_stream_1' not in streams)

    def test_api_valid_property(self):
        # type: () -> None
        """
        Trying to set valid json returns success message.
        """
        test_user = self.example_user('hamlet')
        test_email = test_user.email

        self.login(test_email)
        subs = gather_subscriptions(test_user)[0]
        result = self.client_patch(
            "/api/v1/users/me/subscriptions/%d" % subs[0]["stream_id"],
            {'property': 'color', 'value': '#c2c2c2'},
            **self.api_auth(test_email))
        self.assert_json_success(result)

    def test_api_invalid_property(self):
        # type: () -> None
        """
        Trying to set an invalid property returns a JSON error.
        """

        test_user = self.example_user('hamlet')
        test_email = test_user.email

        self.login(test_email)
        subs = gather_subscriptions(test_user)[0]

        result = self.client_patch(
            "/api/v1/users/me/subscriptions/%d" % subs[0]["stream_id"],
            {'property': 'invalid', 'value': 'somevalue'},
            **self.api_auth(test_email))
        self.assert_json_error(result,
                               "Unknown subscription property: invalid")

    def test_api_invalid_stream_id(self):
        # type: () -> None
        """
        Trying to set an invalid stream id returns a JSON error.
        """
        test_email = self.example_email("hamlet")
        self.login(test_email)
        result = self.client_patch(
            "/api/v1/users/me/subscriptions/121",
            {'property': 'in_home_view', 'value': 'somevalue'},
            **self.api_auth(test_email))
        self.assert_json_error(result,
                               "Invalid stream id")

    def test_bad_add_parameters(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        def check_for_error(val, expected_message):
            # type: (Any, str) -> None
            request = {
                'add': ujson.dumps(val)
            }
            result = self.client_patch(
                "/api/v1/users/me/subscriptions",
                request,
                **self.api_auth(email)
            )
            self.assert_json_error(result, expected_message)

        check_for_error(['foo'], 'add[0] is not a dict')
        check_for_error([{'bogus': 'foo'}], 'name key is missing from add[0]')
        check_for_error([{'name': {}}], 'add[0]["name"] is not a string')

    def test_bad_principals(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        request = {
            'add': ujson.dumps([{'name': 'my_new_stream'}]),
            'principals': ujson.dumps([{}]),
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_error(result, 'principals[0] is not a string')

    def test_bad_delete_parameters(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        request = {
            'delete': ujson.dumps([{'name': 'my_test_stream_1'}])
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_error(result, "delete[0] is not a string")

    def test_add_or_delete_not_specified(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            {},
            **self.api_auth(email)
        )
        self.assert_json_error(result,
                               'Nothing to do. Specify at least one of "add" or "delete".')

    def test_patch_enforces_valid_stream_name_check(self):
        # type: () -> None
        """
        Only way to force an error is with a empty string.
        """
        email = self.example_email('hamlet')
        self.login(email)

        invalid_stream_name = ""
        request = {
            'delete': ujson.dumps([invalid_stream_name])
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_error(result,
                               "Invalid stream name '%s'" % (invalid_stream_name,))

    def test_stream_name_too_long(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        long_stream_name = "a" * 61
        request = {
            'delete': ujson.dumps([long_stream_name])
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_error(result,
                               "Stream name too long (limit: 60 characters)")

    def test_stream_name_contains_null(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        stream_name = "abc\000"
        request = {
            'delete': ujson.dumps([stream_name])
        }
        result = self.client_patch(
            "/api/v1/users/me/subscriptions",
            request,
            **self.api_auth(email)
        )
        self.assert_json_error(result,
                               "Stream name '%s' contains NULL (0x00) characters." % (stream_name))

    def test_compose_views_rollback(self):
        # type: () -> None
        '''
        The compose_views function() is used under the hood by
        update_subscriptions_backend.  It's a pretty simple method in terms of
        control flow, but it uses a Django rollback, which may make it brittle
        code when we upgrade Django.  We test the functions's rollback logic
        here with a simple scenario to avoid false positives related to
        subscription complications.
        '''
        user_profile = self.example_user('hamlet')
        user_profile.full_name = 'Hamlet'
        user_profile.save()

        def method1(req, user_profile):
            # type: (HttpRequest, UserProfile) -> HttpResponse
            user_profile.full_name = 'Should not be committed'
            user_profile.save()
            return json_success()

        def method2(req, user_profile):
            # type: (HttpRequest, UserProfile) -> HttpResponse
            return json_error('random failure')

        with self.assertRaises(JsonableError):
            compose_views(None, user_profile, [(method1, {}), (method2, {})])

        user_profile = self.example_user('hamlet')
        self.assertEqual(user_profile.full_name, 'Hamlet')

class SubscriptionAPITest(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        """
        All tests will be logged in as hamlet. Also save various useful values
        as attributes that tests can access.
        """
        self.user_profile = self.example_user('hamlet')
        self.test_email = self.user_profile.email
        self.login(self.test_email)
        self.test_realm = self.user_profile.realm
        self.streams = self.get_streams(self.test_email, self.test_realm)

    def make_random_stream_names(self, existing_stream_names):
        # type: (List[Text]) -> List[Text]
        """
        Helper function to make up random stream names. It takes
        existing_stream_names and randomly appends a digit to the end of each,
        but avoids names that appear in the list names_to_avoid.
        """
        random_streams = []
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.test_realm)]
        for stream in existing_stream_names:
            random_stream = stream + str(random.randint(0, 9))
            if random_stream not in all_stream_names:
                random_streams.append(random_stream)
        return random_streams

    def test_successful_subscriptions_list(self):
        # type: () -> None
        """
        Calling /api/v1/users/me/subscriptions should successfully return your subscriptions.
        """
        email = self.test_email
        result = self.client_get("/api/v1/users/me/subscriptions", **self.api_auth(email))
        self.assert_json_success(result)
        json = result.json()
        self.assertIn("subscriptions", json)
        for stream in json['subscriptions']:
            self.assertIsInstance(stream['name'], six.string_types)
            self.assertIsInstance(stream['color'], six.string_types)
            self.assertIsInstance(stream['invite_only'], bool)
            # check that the stream name corresponds to an actual
            # stream; will throw Stream.DoesNotExist if it doesn't
            get_stream(stream['name'], self.test_realm)
        list_streams = [stream['name'] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertEqual(sorted(list_streams), sorted(self.streams))

    def helper_check_subs_before_and_after_add(self, subscriptions, other_params,
                                               subscribed, already_subscribed,
                                               email, new_subs, realm, invite_only=False):
        # type: (List[Text], Dict[str, Any], List[Text], List[Text], Text, List[Text], Realm, bool) -> None
        """
        Check result of adding subscriptions.

        You can add subscriptions for yourself or possibly many
        principals, which is why e-mails map to subscriptions in the
        result.

        The result json is of the form

        {"msg": "",
         "result": "success",
         "already_subscribed": {self.example_email("iago"): ["Venice", "Verona"]},
         "subscribed": {self.example_email("iago"): ["Venice8"]}}
        """
        result = self.common_subscribe_to_streams(self.test_email, subscriptions,
                                                  other_params, invite_only=invite_only)
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(sorted(subscribed), sorted(json["subscribed"][email]))
        self.assertEqual(sorted(already_subscribed), sorted(json["already_subscribed"][email]))
        new_streams = self.get_streams(email, realm)
        self.assertEqual(sorted(new_streams), sorted(new_subs))

    def test_successful_subscriptions_add(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and should determine which are new subscriptions vs
        which were already subscribed. We add 2 new streams to the
        list of subscriptions and confirm the right number of events
        are generated.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        add_streams = [u"Verona2", u"Denmark5"]
        self.assertNotEqual(len(add_streams), 0)  # necessary for full test coverage
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            self.helper_check_subs_before_and_after_add(self.streams + add_streams, {},
                                                        add_streams, self.streams, self.test_email,
                                                        self.streams + add_streams, self.test_realm)
        self.assert_length(events, 8)

    def test_successful_subscriptions_add_with_announce(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and should determine which are new subscriptions vs
        which were already subscribed. We add 2 new streams to the
        list of subscriptions and confirm the right number of events
        are generated.
        """
        self.assertNotEqual(len(self.streams), 0)
        add_streams = [u"Verona2", u"Denmark5"]
        self.assertNotEqual(len(add_streams), 0)
        events = []  # type: List[Mapping[str, Any]]
        other_params = {
            'announce': 'true',
        }
        notifications_stream = get_stream(self.streams[0], self.test_realm)
        self.test_realm.notifications_stream = notifications_stream
        self.test_realm.save()

        # Delete the UserProfile from the cache so the realm change will be
        # picked up
        cache.cache_delete(cache.user_profile_by_email_cache_key(self.test_email))
        with tornado_redirected_to_list(events):
            self.helper_check_subs_before_and_after_add(self.streams + add_streams, other_params,
                                                        add_streams, self.streams, self.test_email,
                                                        self.streams + add_streams, self.test_realm)
        self.assertEqual(len(events), 9)

    def test_successful_subscriptions_notifies_pm(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_email("iago")

        current_stream = self.get_streams(invitee, self.test_realm)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]
        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data={
                'announce': 'true',
                'principals': '["%s"]' % (self.user_profile.email,)
            },
        )
        self.assert_json_success(result)

    def test_successful_subscriptions_notifies_stream(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_email("iago")
        invitee_full_name = 'Iago'

        current_stream = self.get_streams(invitee, self.test_realm)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]

        notifications_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.notifications_stream = notifications_stream
        self.test_realm.save()

        # Delete the UserProfile from the cache so the realm change will be
        # picked up
        cache.cache_delete(cache.user_profile_by_email_cache_key(invitee))

        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data=dict(
                announce='true',
                principals='["%s"]' % (self.user_profile.email,)
            ),
        )
        self.assert_json_success(result)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.sender_id, self.notification_bot().id)
        expected_msg = "%s just created a new stream #**%s**." % (invitee_full_name, invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_successful_cross_realm_notification(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions in a new realm
        should notify with a proper new stream link
        """
        realm = do_create_realm("testrealm", "Test Realm")

        notifications_stream = Stream.objects.get(name='announce', realm=realm)
        realm.notifications_stream = notifications_stream
        realm.save()

        invite_streams = ["cross_stream"]

        user = self.example_user('AARON')
        user.realm = realm
        user.save()

        # Delete the UserProfile from the cache so the realm change will be
        # picked up
        cache.cache_delete(cache.user_profile_by_email_cache_key(user.email))

        result = self.common_subscribe_to_streams(
            user.email,
            invite_streams,
            extra_post_data=dict(
                announce='true'
            ),
            subdomain="testrealm",
        )
        self.assert_json_success(result)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.sender_id, self.notification_bot().id)
        stream_id = Stream.objects.latest('id').id
        expected_rendered_msg = '<p>%s just created a new stream <a class="stream" data-stream-id="%d" href="/#narrow/stream/%s">#%s</a>.</p>' % (
            user.full_name, stream_id, invite_streams[0], invite_streams[0])
        self.assertEqual(msg.rendered_content, expected_rendered_msg)

    def test_successful_subscriptions_notifies_with_escaping(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_email("iago")
        invitee_full_name = 'Iago'

        current_stream = self.get_streams(invitee, self.test_realm)[0]
        notifications_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.notifications_stream = notifications_stream
        self.test_realm.save()

        invite_streams = ['strange ) \\ test']
        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data={
                'announce': 'true',
                'principals': '["%s"]' % (self.user_profile.email,)
            },
        )
        self.assert_json_success(result)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.sender_id, self.notification_bot().id)
        expected_msg = "%s just created a new stream #**%s**." % (invitee_full_name, invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_non_ascii_stream_subscription(self):
        # type: () -> None
        """
        Subscribing to a stream name with non-ASCII characters succeeds.
        """
        self.helper_check_subs_before_and_after_add(self.streams + [u"hümbüǵ"], {},
                                                    [u"hümbüǵ"], self.streams, self.test_email,
                                                    self.streams + [u"hümbüǵ"], self.test_realm)

    def test_subscriptions_add_too_long(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions on a stream whose name is >60
        characters should return a JSON error.
        """
        # character limit is 60 characters
        long_stream_name = "a" * 61
        result = self.common_subscribe_to_streams(self.test_email, [long_stream_name])
        self.assert_json_error(result,
                               "Stream name too long (limit: 60 characters)")

    def test_subscriptions_add_stream_with_null(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions on a stream whose name contains
        null characters should return a JSON error.
        """
        stream_name = "abc\000"
        result = self.common_subscribe_to_streams(self.test_email, [stream_name])
        self.assert_json_error(result,
                               "Stream name '%s' contains NULL (0x00) characters." % (stream_name))

    def test_user_settings_for_adding_streams(self):
        # type: () -> None
        with mock.patch('zerver.models.UserProfile.can_create_streams', return_value=False):
            result = self.common_subscribe_to_streams(self.test_email, ['stream1'])
            self.assert_json_error(result, 'User cannot create streams.')

        with mock.patch('zerver.models.UserProfile.can_create_streams', return_value=True):
            result = self.common_subscribe_to_streams(self.test_email, ['stream2'])
            self.assert_json_success(result)

        # User should still be able to subscribe to an existing stream
        with mock.patch('zerver.models.UserProfile.can_create_streams', return_value=False):
            result = self.common_subscribe_to_streams(self.test_email, ['stream2'])
            self.assert_json_success(result)

    def test_subscriptions_add_invalid_stream(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid name is the empty string
        invalid_stream_name = ""
        result = self.common_subscribe_to_streams(self.test_email, [invalid_stream_name])
        self.assert_json_error(result,
                               "Invalid stream name '%s'" % (invalid_stream_name,))

    def assert_adding_subscriptions_for_principal(self, invitee_email, invitee_realm, streams, invite_only=False):
        # type: (Text, Realm, List[Text], bool) -> None
        """
        Calling POST /json/users/me/subscriptions on behalf of another principal (for
        whom you have permission to add subscriptions) should successfully add
        those subscriptions and send a message to the subscribee notifying
        them.
        """
        other_profile = get_user(invitee_email, invitee_realm)
        current_streams = self.get_streams(invitee_email, invitee_realm)
        self.assertIsInstance(other_profile, UserProfile)
        self.assertNotEqual(len(current_streams), 0)  # necessary for full test coverage
        self.assertNotEqual(len(streams), 0)  # necessary for full test coverage
        streams_to_sub = streams[:1]  # just add one, to make the message easier to check
        streams_to_sub.extend(current_streams)
        self.helper_check_subs_before_and_after_add(streams_to_sub,
                                                    {"principals": ujson.dumps([invitee_email])}, streams[:1],
                                                    current_streams, invitee_email, streams_to_sub,
                                                    invitee_realm, invite_only=invite_only)

        # verify that a welcome message was sent to the stream
        msg = self.get_last_message()
        self.assertEqual(msg.recipient.type, msg.recipient.STREAM)
        self.assertEqual(msg.subject, u'hello')
        self.assertEqual(msg.sender.email, settings.WELCOME_BOT)
        self.assertIn('Welcome to #**', msg.content)

    def test_multi_user_subscription(self):
        # type: () -> None
        email1 = self.example_email("cordelia")
        email2 = self.example_email("iago")
        realm = get_realm("zulip")
        streams_to_sub = ['multi_user_stream']
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_email,
                    streams_to_sub,
                    dict(principals=ujson.dumps([email1, email2])),
                )
        self.assert_length(queries, 39)

        self.assert_length(events, 7)
        for ev in [x for x in events if x['event']['type'] not in ('message', 'stream')]:
            if isinstance(ev['event']['subscriptions'][0], dict):
                self.assertEqual(ev['event']['op'], 'add')
                self.assertEqual(
                    set(ev['event']['subscriptions'][0]['subscribers']),
                    set([email1, email2])
                )
            else:
                # Check "peer_add" events for streams users were
                # never subscribed to, in order for the neversubscribed
                # structure to stay up-to-date.
                self.assertEqual(ev['event']['op'], 'peer_add')

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(stream.num_subscribers(), 2)

        # Now add ourselves
        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_email,
                    streams_to_sub,
                    dict(principals=ujson.dumps([self.test_email])),
                )
        self.assert_length(queries, 15)

        self.assert_length(events, 2)
        add_event, add_peer_event = events
        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user(self.test_email, self.test_realm).id])
        self.assertEqual(
            set(add_event['event']['subscriptions'][0]['subscribers']),
            set([email1, email2, self.test_email])
        )

        self.assertEqual(len(add_peer_event['users']), 17)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], self.user_profile.id)

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(stream.num_subscribers(), 3)

        # Finally, add othello.
        events = []
        user_profile = self.example_user('othello')
        email3 = user_profile.email
        realm3 = user_profile.realm
        stream = get_stream('multi_user_stream', realm)
        with tornado_redirected_to_list(events):
            bulk_add_subscriptions([stream], [user_profile])

        self.assert_length(events, 2)
        add_event, add_peer_event = events

        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user(email3, realm3).id])
        self.assertEqual(
            set(add_event['event']['subscriptions'][0]['subscribers']),
            set([email1, email2, email3, self.test_email])
        )

        # We don't send a peer_add event to othello
        self.assertNotIn(user_profile.id, add_peer_event['users'])
        self.assertEqual(len(add_peer_event['users']), 17)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], user_profile.id)

    def test_private_stream_subscription(self):
        # type: () -> None
        realm = get_realm("zulip")

        # Create a private stream with Hamlet subscribed
        stream_name = "private"
        (stream, _) = create_stream_if_needed(realm, stream_name, invite_only=True)

        existing_user_profile = self.example_user('hamlet')
        bulk_add_subscriptions([stream], [existing_user_profile])

        # Now subscribe Cordelia to the stream, capturing events
        user_profile = self.example_user('cordelia')

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            bulk_add_subscriptions([stream], [user_profile])

        self.assert_length(events, 3)
        create_event, add_event, add_peer_event = events

        self.assertEqual(create_event['event']['type'], 'stream')
        self.assertEqual(create_event['event']['op'], 'create')
        self.assertEqual(create_event['users'], [user_profile.id])
        self.assertEqual(create_event['event']['streams'][0]['name'], stream_name)

        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [user_profile.id])
        self.assertEqual(
            set(add_event['event']['subscriptions'][0]['subscribers']),
            set([user_profile.email, existing_user_profile.email])
        )

        # We don't send a peer_add event to othello
        self.assertNotIn(user_profile.id, add_peer_event['users'])
        self.assertEqual(len(add_peer_event['users']), 1)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], user_profile.id)

    def test_users_getting_add_peer_event(self):
        # type: () -> None
        """
        Check users getting add_peer_event is correct
        """
        streams_to_sub = ['multi_user_stream']
        orig_emails_to_subscribe = [self.test_email, self.example_email("othello")]
        self.common_subscribe_to_streams(
            self.test_email,
            streams_to_sub,
            dict(principals=ujson.dumps(orig_emails_to_subscribe)))

        new_emails_to_subscribe = [self.example_email("iago"), self.example_email("cordelia")]
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            self.common_subscribe_to_streams(
                self.test_email,
                streams_to_sub,
                dict(principals=ujson.dumps(new_emails_to_subscribe)),
            )

        add_peer_events = [events[2], events[3]]
        for add_peer_event in add_peer_events:
            self.assertEqual(add_peer_event['event']['type'], 'subscription')
            self.assertEqual(add_peer_event['event']['op'], 'peer_add')
            event_sent_to_ids = add_peer_event['users']
            sent_emails = [
                get_user_profile_by_id(user_id).email
                for user_id in event_sent_to_ids]
            for email in new_emails_to_subscribe:
                # Make sure new users subscribed to stream is not in
                # peer_add event recipient list
                self.assertNotIn(email, sent_emails)
            for old_user in orig_emails_to_subscribe:
                # Check non new users are in peer_add event recipient list.
                self.assertIn(old_user, sent_emails)

    def test_users_getting_remove_peer_event(self):
        # type: () -> None
        """
        Check users getting add_peer_event is correct
        """
        user1 = self.example_user("othello")
        user2 = self.example_user("cordelia")
        user3 = self.example_user("hamlet")
        user4 = self.example_user("iago")

        stream1 = self.make_stream('stream1')
        stream2 = self.make_stream('stream2')
        private = self.make_stream('private_stream', invite_only=True)

        self.subscribe(user1, 'stream1')
        self.subscribe(user2, 'stream1')
        self.subscribe(user3, 'stream1')

        self.subscribe(user2, 'stream2')

        self.subscribe(user1, 'private_stream')
        self.subscribe(user2, 'private_stream')
        self.subscribe(user3, 'private_stream')

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            bulk_remove_subscriptions(
                users=[user1, user2],
                streams=[stream1, stream2, private]
            )

        peer_events = [e for e in events
                       if e['event'].get('op') == 'peer_remove']

        notifications = set()
        for event in peer_events:
            for user_id in event['users']:
                for stream_name in event['event']['subscriptions']:
                    removed_user_id = event['event']['user_id']
                    notifications.add((user_id, removed_user_id, stream_name))

        # POSITIVE CASES FIRST
        self.assertIn((user3.id, user1.id, 'stream1'), notifications)
        self.assertIn((user4.id, user1.id, 'stream1'), notifications)

        self.assertIn((user3.id, user2.id, 'stream1'), notifications)
        self.assertIn((user4.id, user2.id, 'stream1'), notifications)

        self.assertIn((user1.id, user2.id, 'stream2'), notifications)
        self.assertIn((user3.id, user2.id, 'stream2'), notifications)
        self.assertIn((user4.id, user2.id, 'stream2'), notifications)

        self.assertIn((user3.id, user1.id, 'private_stream'), notifications)
        self.assertIn((user3.id, user2.id, 'private_stream'), notifications)

        # NEGATIVE

        # don't be notified if you are being removed yourself
        self.assertNotIn((user1.id, user1.id, 'stream1'), notifications)

        # don't send false notifications for folks that weren't actually
        # subscribed int he first place
        self.assertNotIn((user3.id, user1.id, 'stream2'), notifications)

        # don't send notifications for random people
        self.assertNotIn((user3.id, user4.id, 'stream2'), notifications)

        # don't send notifications to unsubscribed people for private streams
        self.assertNotIn((user4.id, user1.id, 'private_stream'), notifications)

    def test_bulk_subscribe_MIT(self):
        # type: () -> None
        realm = get_realm("zephyr")
        streams = ["stream_%s" % i for i in range(40)]
        for stream_name in streams:
            self.make_stream(stream_name, realm=realm)

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.mit_email("starnine"),
                    streams,
                    dict(principals=ujson.dumps([self.mit_email("starnine")])),
                    subdomain="zephyr",
                )
        # Make sure Zephyr mirroring realms such as MIT do not get
        # any tornado subscription events
        self.assert_length(events, 0)
        self.assert_length(queries, 8)

    def test_bulk_subscribe_many(self):
        # type: () -> None

        # Create a whole bunch of streams
        streams = ["stream_%s" % i for i in range(20)]
        for stream_name in streams:
            self.make_stream(stream_name)

        with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_email,
                    streams,
                    dict(principals=ujson.dumps([self.test_email])),
                )
        # Make sure we don't make O(streams) queries
        self.assert_length(queries, 19)

    @slow("common_subscribe_to_streams is slow")
    def test_subscriptions_add_for_principal(self):
        # type: () -> None
        """
        You can subscribe other people to streams.
        """
        invitee_email = self.example_email("iago")
        invitee_realm = get_realm('zulip')
        current_streams = self.get_streams(invitee_email, invitee_realm)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee_email, invitee_realm, invite_streams)

    @slow("common_subscribe_to_streams is slow")
    def test_subscriptions_add_for_principal_invite_only(self):
        # type: () -> None
        """
        You can subscribe other people to invite only streams.
        """
        invitee_email = self.example_email("iago")
        invitee_realm = get_realm('zulip')
        current_streams = self.get_streams(invitee_email, invitee_realm)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee_email, invitee_realm, invite_streams,
                                                       invite_only=True)

    @slow("common_subscribe_to_streams is slow")
    def test_non_ascii_subscription_for_principal(self):
        # type: () -> None
        """
        You can subscribe other people to streams even if they containing
        non-ASCII characters.
        """
        self.assert_adding_subscriptions_for_principal(self.example_email("iago"), get_realm('zulip'), [u"hümbüǵ"])

    def test_subscription_add_invalid_principal(self):
        # type: () -> None
        """
        Calling subscribe on behalf of a principal that does not exist
        should return a JSON error.
        """
        invalid_principal = "rosencrantz-and-guildenstern@zulip.com"
        invalid_principal_realm = get_realm("zulip")
        # verify that invalid_principal actually doesn't exist
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user(invalid_principal, invalid_principal_realm)
        result = self.common_subscribe_to_streams(self.test_email, self.streams,
                                                  {"principals": ujson.dumps([invalid_principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (invalid_principal,), status_code=403)

    def test_subscription_add_principal_other_realm(self):
        # type: () -> None
        """
        Calling subscribe on behalf of a principal in another realm
        should return a JSON error.
        """
        profile = self.mit_user('starnine')
        principal = profile.email
        # verify that principal exists (thus, the reason for the error is the cross-realming)
        self.assertIsInstance(profile, UserProfile)
        result = self.common_subscribe_to_streams(self.test_email, self.streams,
                                                  {"principals": ujson.dumps([principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (principal,), status_code=403)

    def helper_check_subs_before_and_after_remove(self, subscriptions, json_dict,
                                                  email, new_subs, realm):
        # type: (List[Text], Dict[str, Any], Text, List[Text], Realm) -> None
        """
        Check result of removing subscriptions.

        Unlike adding subscriptions, you can only remove subscriptions
        for yourself, so the result format is different.

        {"msg": "",
         "removed": ["Denmark", "Scotland", "Verona"],
         "not_subscribed": ["Rome"], "result": "success"}
        """
        result = self.client_delete("/json/users/me/subscriptions",
                                    {"subscriptions": ujson.dumps(subscriptions)})
        self.assert_json_success(result)
        json = result.json()
        for key, val in six.iteritems(json_dict):
            self.assertEqual(sorted(val), sorted(json[key]))  # we don't care about the order of the items
        new_streams = self.get_streams(email, realm)
        self.assertEqual(sorted(new_streams), sorted(new_subs))

    def test_successful_subscriptions_remove(self):
        # type: () -> None
        """
        Calling DELETE /json/users/me/subscriptions should successfully remove streams,
        and should determine which were removed vs which weren't subscribed to.
        We cannot randomly generate stream names because the remove code
        verifies whether streams exist.
        """
        self.assertGreaterEqual(len(self.streams), 2)
        streams_to_remove = self.streams[1:]
        not_subbed = []
        for stream in Stream.objects.all():
            if stream.name not in self.streams:
                not_subbed.append(stream.name)
        random.shuffle(not_subbed)
        self.assertNotEqual(len(not_subbed), 0)  # necessary for full test coverage
        try_to_remove = not_subbed[:3]  # attempt to remove up to 3 streams not already subbed to
        streams_to_remove.extend(try_to_remove)
        self.helper_check_subs_before_and_after_remove(streams_to_remove,
                                                       {"removed": self.streams[1:], "not_subscribed": try_to_remove},
                                                       self.test_email, [self.streams[0]], self.test_realm)

    def test_subscriptions_remove_fake_stream(self):
        # type: () -> None
        """
        Calling DELETE /json/users/me/subscriptions on a stream that doesn't exist
        should return a JSON error.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        streams_to_remove = random_streams[:1]  # pick only one fake stream, to make checking the error message easy
        result = self.client_delete("/json/users/me/subscriptions",
                                    {"subscriptions": ujson.dumps(streams_to_remove)})
        self.assert_json_error(result, "Stream(s) (%s) do not exist" % (random_streams[0],))

    def helper_subscriptions_exists(self, stream, expect_success, subscribed):
        # type: (Text, bool, bool) -> None
        """
        Call /json/subscriptions/exists on a stream and expect a certain result.
        """
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream})
        json = result.json()
        if expect_success:
            self.assert_json_success(result)
        else:
            self.assertEqual(result.status_code, 404)
        if subscribed:
            self.assertIn("subscribed", json)
            self.assertEqual(json["subscribed"], subscribed)

    def test_successful_subscriptions_exists_subbed(self):
        # type: () -> None
        """
        Calling /json/subscriptions/exist on a stream to which you are subbed
        should return that it exists and that you are subbed.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(self.streams[0], True, True)

    def test_successful_subscriptions_exists_not_subbed(self):
        # type: () -> None
        """
        Calling /json/subscriptions/exist on a stream to which you are not
        subbed should return that it exists and that you are not subbed.
        """
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.test_realm)]
        streams_not_subbed = list(set(all_stream_names) - set(self.streams))
        self.assertNotEqual(len(streams_not_subbed), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(streams_not_subbed[0], True, False)

    def test_subscriptions_does_not_exist(self):
        # type: () -> None
        """
        Calling /json/subscriptions/exist on a stream that doesn't exist should
        return that it doesn't exist.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(random_streams[0], False, False)

    def test_subscriptions_exist_invalid_name(self):
        # type: () -> None
        """
        Calling /json/subscriptions/exist on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid stream name is the empty string
        invalid_stream_name = ""
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": invalid_stream_name})
        self.assert_json_error(result, "Invalid stream name ''")

    def test_existing_subscriptions_autosubscription(self):
        # type: () -> None
        """
        Call /json/subscriptions/exist on an existing stream and autosubscribe to it.
        """
        stream_name = "new_public_stream"
        result = self.common_subscribe_to_streams(self.example_email("cordelia"), [stream_name],
                                                  invite_only=False)
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "false"})
        self.assert_json_success(result)
        self.assertIn("subscribed", result.json())
        self.assertFalse(result.json()["subscribed"])

        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "true"})
        self.assert_json_success(result)
        self.assertIn("subscribed", result.json())
        self.assertTrue(result.json()["subscribed"])

    def test_existing_subscriptions_autosubscription_private_stream(self):
        # type: () -> None
        """Call /json/subscriptions/exist on an existing private stream with
        autosubscribe should fail.
        """
        stream_name = "Saxony"
        result = self.common_subscribe_to_streams(self.example_email("cordelia"), [stream_name],
                                                  invite_only=True)
        stream = get_stream(stream_name, self.test_realm)

        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "true"})
        # We can't see invite-only streams here
        self.assert_json_error(result, "Invalid stream name 'Saxony'", status_code=404)
        # Importantly, we are not now subscribed
        self.assertEqual(Subscription.objects.filter(
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id).count(), 1)

        # A user who is subscribed still sees the stream exists
        self.login(self.example_email("cordelia"))
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "false"})
        self.assert_json_success(result)
        self.assertIn("subscribed", result.json())
        self.assertTrue(result.json()["subscribed"])

    def get_subscription(self, user_profile, stream_name):
        # type: (UserProfile, Text) -> Subscription
        stream = get_stream(stream_name, self.test_realm)
        return Subscription.objects.get(
            user_profile=user_profile,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id,
        )

    def test_subscriptions_add_notification_default_true(self):
        # type: () -> None
        """
        When creating a subscription, the desktop, push, and audible notification
        settings for that stream are derived from the global notification
        settings.
        """
        user_profile = self.example_user('iago')
        invitee_email = user_profile.email
        invitee_realm = user_profile.realm
        user_profile.enable_stream_desktop_notifications = True
        user_profile.enable_stream_push_notifications = True
        user_profile.enable_stream_sounds = True
        user_profile.save()
        current_stream = self.get_streams(invitee_email, invitee_realm)[0]
        invite_streams = self.make_random_stream_names([current_stream])
        self.assert_adding_subscriptions_for_principal(invitee_email, invitee_realm, invite_streams)
        subscription = self.get_subscription(user_profile, invite_streams[0])

        with mock.patch('zerver.models.Recipient.__unicode__', return_value='recip'):
            self.assertEqual(str(subscription),
                             u'<Subscription: '
                             '<UserProfile: %s <Realm: zulip 1>> -> recip>' % (self.example_email('iago'),))

        self.assertTrue(subscription.desktop_notifications)
        self.assertTrue(subscription.push_notifications)
        self.assertTrue(subscription.audible_notifications)

    def test_subscriptions_add_notification_default_false(self):
        # type: () -> None
        """
        When creating a subscription, the desktop, push, and audible notification
        settings for that stream are derived from the global notification
        settings.
        """
        user_profile = self.example_user('iago')
        invitee_email = user_profile.email
        invitee_realm = user_profile.realm
        user_profile.enable_stream_desktop_notifications = False
        user_profile.enable_stream_push_notifications = False
        user_profile.enable_stream_sounds = False
        user_profile.save()
        current_stream = self.get_streams(invitee_email, invitee_realm)[0]
        invite_streams = self.make_random_stream_names([current_stream])
        self.assert_adding_subscriptions_for_principal(invitee_email, invitee_realm, invite_streams)
        subscription = self.get_subscription(user_profile, invite_streams[0])
        self.assertFalse(subscription.desktop_notifications)
        self.assertFalse(subscription.push_notifications)
        self.assertFalse(subscription.audible_notifications)


class GetPublicStreamsTest(ZulipTestCase):

    def test_public_streams_api(self):
        # type: () -> None
        """
        Ensure that the query we use to get public streams successfully returns
        a list of streams
        """
        email = self.example_email('hamlet')
        realm = get_realm('zulip')
        self.login(email)

        # Check it correctly lists the user's subs with include_public=false
        result = self.client_get("/api/v1/streams?include_public=false", **self.api_auth(email))
        result2 = self.client_get("/api/v1/users/me/subscriptions", **self.api_auth(email))

        self.assert_json_success(result)
        json = result.json()

        self.assertIn("streams", json)

        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(result2)
        json2 = ujson.loads(result2.content)

        self.assertEqual(sorted([s["name"] for s in json["streams"]]),
                         sorted([s["name"] for s in json2["subscriptions"]]))

        # Check it correctly lists all public streams with include_subscribed=false
        result = self.client_get("/api/v1/streams?include_public=true&include_subscribed=false",
                                 **self.api_auth(email))
        self.assert_json_success(result)

        json = result.json()
        all_streams = [stream.name for stream in
                       Stream.objects.filter(realm=realm)]
        self.assertEqual(sorted(s["name"] for s in json["streams"]),
                         sorted(all_streams))

        # Check non-superuser can't use include_all_active
        result = self.client_get("/api/v1/streams?include_all_active=true",
                                 **self.api_auth(email))
        self.assertEqual(result.status_code, 400)

class StreamIdTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email
        self.login(self.email)

    def test_get_stream_id(self):
        # type: () -> None
        stream = gather_subscriptions(self.user_profile)[0][0]
        result = self.client_get("/json/get_stream_id?stream=%s" % (stream['name'],))
        self.assert_json_success(result)
        self.assertEqual(result.json()['stream_id'], stream['stream_id'])

    def test_get_stream_id_wrong_name(self):
        # type: () -> None
        result = self.client_get("/json/get_stream_id?stream=wrongname")
        self.assert_json_error(result, u"Invalid stream name 'wrongname'")

class InviteOnlyStreamTest(ZulipTestCase):
    def test_must_be_subbed_to_send(self):
        # type: () -> None
        """
        If you try to send a message to an invite-only stream to which
        you aren't subscribed, you'll get a 400.
        """
        self.login(self.example_email("hamlet"))
        # Create Saxony as an invite-only stream.
        self.assert_json_success(
            self.common_subscribe_to_streams(self.example_email("hamlet"), ["Saxony"],
                                             invite_only=True))

        email = self.example_email("cordelia")
        with self.assertRaises(JsonableError):
            self.send_message(email, "Saxony", Recipient.STREAM)

    def test_list_respects_invite_only_bit(self):
        # type: () -> None
        """
        Make sure that /api/v1/users/me/subscriptions properly returns
        the invite-only bit for streams that are invite-only
        """
        email = self.example_email('hamlet')
        self.login(email)

        result1 = self.common_subscribe_to_streams(email, ["Saxony"], invite_only=True)
        self.assert_json_success(result1)
        result2 = self.common_subscribe_to_streams(email, ["Normandy"], invite_only=False)
        self.assert_json_success(result2)
        result = self.client_get("/api/v1/users/me/subscriptions", **self.api_auth(email))
        self.assert_json_success(result)
        self.assertIn("subscriptions", result.json())
        for sub in result.json()["subscriptions"]:
            if sub['name'] == "Normandy":
                self.assertEqual(sub['invite_only'], False, "Normandy was mistakenly marked invite-only")
            if sub['name'] == "Saxony":
                self.assertEqual(sub['invite_only'], True, "Saxony was not properly marked invite-only")

    @slow("lots of queries")
    def test_inviteonly(self):
        # type: () -> None
        # Creating an invite-only stream is allowed
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        stream_name = "Saxony"

        result = self.common_subscribe_to_streams(email, [stream_name], invite_only=True)
        self.assert_json_success(result)

        json = result.json()
        self.assertEqual(json["subscribed"], {email: [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is not allowed
        user_profile = self.example_user('othello')
        email = user_profile.email
        self.login(email)
        result = self.common_subscribe_to_streams(email, [stream_name])
        self.assert_json_error(result, 'Unable to access stream (Saxony).')

        # authorization_errors_fatal=False works
        user_profile = self.example_user('othello')
        email = user_profile.email
        self.login(email)
        result = self.common_subscribe_to_streams(email, [stream_name],
                                                  extra_post_data={'authorization_errors_fatal': ujson.dumps(False)})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json["unauthorized"], [stream_name])
        self.assertEqual(json["subscribed"], {})
        self.assertEqual(json["already_subscribed"], {})

        # Inviting another user to an invite-only stream is allowed
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        result = self.common_subscribe_to_streams(
            email, [stream_name],
            extra_post_data={'principals': ujson.dumps([self.example_email("othello")])})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json["subscribed"], {self.example_email("othello"): [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Make sure both users are subscribed to this stream
        stream_id = get_stream(stream_name, user_profile.realm).id
        result = self.client_get("/api/v1/streams/%d/members" % (stream_id,),
                                 **self.api_auth(email))
        self.assert_json_success(result)
        json = result.json()

        self.assertTrue(self.example_email("othello") in json['subscribers'])
        self.assertTrue(self.example_email('hamlet') in json['subscribers'])

class GetSubscribersTest(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email
        self.login(self.email)

    def assert_user_got_subscription_notification(self, expected_msg):
        # type: (Text) -> None
        # verify that the user was sent a message informing them about the subscription
        msg = self.get_last_message()
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id, self.notification_bot().id)

        def non_ws(s):
            # type: (Text) -> Text
            return s.replace('\n', '').replace(' ', '')

        self.assertEqual(non_ws(msg.content), non_ws(expected_msg))

    def check_well_formed_result(self, result, stream_name, realm):
        # type: (Dict[str, Any], Text, Realm) -> None
        """
        A successful call to get_subscribers returns the list of subscribers in
        the form:

        {"msg": "",
         "result": "success",
         "subscribers": [self.example_email("hamlet"), self.example_email("prospero")]}
        """
        self.assertIn("subscribers", result)
        self.assertIsInstance(result["subscribers"], list)
        true_subscribers = [user_profile.email for user_profile in self.users_subscribed_to_stream(
            stream_name, realm)]
        self.assertEqual(sorted(result["subscribers"]), sorted(true_subscribers))

    def make_subscriber_request(self, stream_id, email=None):
        # type: (int, Optional[Text]) -> HttpResponse
        if email is None:
            email = self.email
        return self.client_get("/api/v1/streams/%d/members" % (stream_id,),
                               **self.api_auth(email))

    def make_successful_subscriber_request(self, stream_name):
        # type: (Text) -> None
        stream_id = get_stream(stream_name, self.user_profile.realm).id
        result = self.make_subscriber_request(stream_id)
        self.assert_json_success(result)
        self.check_well_formed_result(result.json(),
                                      stream_name, self.user_profile.realm)

    def test_subscriber(self):
        # type: () -> None
        """
        get_subscribers returns the list of subscribers.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]['name']
        self.make_successful_subscriber_request(stream_name)

    @slow("common_subscribe_to_streams is slow")
    def test_gather_subscriptions(self):
        # type: () -> None
        """
        gather_subscriptions returns correct results with only 3 queries

        (We also use this test to verify subscription notifications to
        folks who get subscribed to streams.)
        """
        streams = ["stream_%s" % i for i in range(10)]
        for stream_name in streams:
            self.make_stream(stream_name)

        users_to_subscribe = [self.email, self.example_email("othello"), self.example_email("cordelia")]
        ret = self.common_subscribe_to_streams(
            self.email,
            streams,
            dict(principals=ujson.dumps(users_to_subscribe)))

        self.assert_json_success(ret)

        msg = '''
            Hi there!  We thought you'd like to know that King Hamlet
            just subscribed you to the following streams:

            * #**stream_0**
            * #**stream_1**
            * #**stream_2**
            * #**stream_3**
            * #**stream_4**
            * #**stream_5**
            * #**stream_6**
            * #**stream_7**
            * #**stream_8**
            * #**stream_9**

            You can see historical content on a non-invite-only stream by narrowing to it.
            '''

        self.assert_user_got_subscription_notification(msg)

        # Subscribe ourself first.
        ret = self.common_subscribe_to_streams(
            self.email,
            ["stream_invite_only_1"],
            dict(principals=ujson.dumps([self.email])),
            invite_only=True)
        self.assert_json_success(ret)

        # Now add in other users, and this should trigger messages
        # to notify the user.
        ret = self.common_subscribe_to_streams(
            self.email,
            ["stream_invite_only_1"],
            dict(principals=ujson.dumps(users_to_subscribe)),
            invite_only=True)
        self.assert_json_success(ret)

        msg = '''
            Hi there!  We thought you'd like to know that King Hamlet
            just subscribed you to the **invite-only** stream
            #**stream_invite_only_1**.
            '''
        self.assert_user_got_subscription_notification(msg)

        with queries_captured() as queries:
            subscriptions = gather_subscriptions(self.user_profile)
        self.assertTrue(len(subscriptions[0]) >= 11)
        for sub in subscriptions[0]:
            if not sub["name"].startswith("stream_"):
                continue
            self.assertTrue(len(sub["subscribers"]) == len(users_to_subscribe))
        self.assert_length(queries, 6)

    @slow("common_subscribe_to_streams is slow")
    def test_never_subscribed_streams(self):
        # type: () -> None
        """
        Check never_subscribed streams are fetched correctly and not include invite_only streams.
        """
        realm = get_realm("zulip")
        users_to_subscribe = [
            self.example_email("othello"),
            self.example_email("cordelia"),
        ]

        public_streams = [
            'test_stream_public_1',
            'test_stream_public_2',
            'test_stream_public_3',
            'test_stream_public_4',
            'test_stream_public_5',
        ]

        private_streams = [
            'test_stream_invite_only_1',
            'test_stream_invite_only_2',
        ]

        def create_public_streams():
            # type: () -> None
            for stream_name in public_streams:
                self.make_stream(stream_name, realm=realm)

            ret = self.common_subscribe_to_streams(
                self.email,
                public_streams,
                dict(principals=ujson.dumps(users_to_subscribe))
            )
            self.assert_json_success(ret)

        create_public_streams()

        def create_private_streams():
            # type: () -> None
            ret = self.common_subscribe_to_streams(
                self.email,
                private_streams,
                dict(principals=ujson.dumps(users_to_subscribe)),
                invite_only=True
            )
            self.assert_json_success(ret)

        create_private_streams()

        def get_never_subscribed():
            # type: () -> List[Dict[str, Any]]
            with queries_captured() as queries:
                sub_data = gather_subscriptions_helper(self.user_profile)
            never_subscribed = sub_data[2]
            self.assert_length(queries, 5)

            # Ignore old streams.
            never_subscribed = [
                dct for dct in never_subscribed
                if dct['name'].startswith('test_')
            ]
            return never_subscribed

        never_subscribed = get_never_subscribed()

        # Invite only stream should not be there in never_subscribed streams
        self.assertEqual(len(never_subscribed), len(public_streams))
        for stream_dict in never_subscribed:
            name = stream_dict['name']
            self.assertFalse('invite_only' in name)
            self.assertTrue(len(stream_dict["subscribers"]) == len(users_to_subscribe))

        def test_admin_case():
            # type: () -> None
            self.user_profile.is_realm_admin = True
            never_subscribed = get_never_subscribed()

            self.assertEqual(
                len(never_subscribed),
                len(public_streams) + len(private_streams)
            )
            for stream_dict in never_subscribed:
                name = stream_dict['name']
                if 'invite_only' in name:
                    self.assertFalse('subscribers' in stream_dict)
                else:
                    self.assertTrue(len(stream_dict["subscribers"]) == len(users_to_subscribe))

        test_admin_case()

    @slow("common_subscribe_to_streams is slow")
    def test_gather_subscriptions_mit(self):
        # type: () -> None
        """
        gather_subscriptions returns correct results with only 3 queries
        """
        # Subscribe only ourself because invites are disabled on mit.edu
        mit_user_profile = self.mit_user('starnine')
        email = mit_user_profile.email
        users_to_subscribe = [email, self.mit_email("espuser")]
        for email in users_to_subscribe:
            self.subscribe(get_user(email, mit_user_profile.realm), "mit_stream")

        ret = self.common_subscribe_to_streams(
            email,
            ["mit_invite_only"],
            dict(principals=ujson.dumps(users_to_subscribe)),
            invite_only=True,
            subdomain="zephyr")
        self.assert_json_success(ret)

        with queries_captured() as queries:
            subscriptions = gather_subscriptions(mit_user_profile)

        self.assertTrue(len(subscriptions[0]) >= 2)
        for sub in subscriptions[0]:
            if not sub["name"].startswith("mit_"):
                raise AssertionError("Unexpected stream!")
            if sub["name"] == "mit_invite_only":
                self.assertTrue(len(sub["subscribers"]) == len(users_to_subscribe))
            else:
                self.assertTrue(len(sub["subscribers"]) == 0)
        self.assert_length(queries, 5)

    def test_nonsubscriber(self):
        # type: () -> None
        """
        Even a non-subscriber to a public stream can query a stream's membership
        with get_subscribers.
        """
        # Create a stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name])
        other_email = self.example_email("othello")

        # Fetch the subscriber list as a non-member.
        self.login(other_email)
        self.make_successful_subscriber_request(stream_name)

    def test_subscriber_private_stream(self):
        # type: () -> None
        """
        A subscriber to a private stream can query that stream's membership.
        """
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name],
                                         invite_only=True)
        self.make_successful_subscriber_request(stream_name)

    def test_json_get_subscribers_stream_not_exist(self):
        # type: () -> None
        """
        json_get_subscribers also returns the list of subscribers for a stream.
        """
        stream_id = 99999999
        result = self.client_get("/json/streams/%d/members" % (stream_id,))
        self.assert_json_error(result, u'Invalid stream id')

    def test_json_get_subscribers(self):
        # type: () -> None
        """
        json_get_subscribers in zerver/views/streams.py
        also returns the list of subscribers for a stream.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]['name']
        stream_id = get_stream(stream_name, self.user_profile.realm).id
        expected_subscribers = gather_subscriptions(self.user_profile)[0][0]['subscribers']
        result = self.client_get("/json/streams/%d/members" % (stream_id,))
        self.assert_json_success(result)
        result_dict = result.json()
        self.assertIn('subscribers', result_dict)
        self.assertIsInstance(result_dict['subscribers'], list)
        subscribers = []  # type: List[Text]
        for subscriber in result_dict['subscribers']:
            self.assertIsInstance(subscriber, six.string_types)
            subscribers.append(subscriber)
        self.assertEqual(set(subscribers), set(expected_subscribers))

    def test_nonsubscriber_private_stream(self):
        # type: () -> None
        """
        A non-subscriber to a private stream can't query that stream's membership.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        stream_name = "NewStream"
        self.common_subscribe_to_streams(self.email, [stream_name],
                                         invite_only=True)
        user_profile = self.example_user('othello')
        other_email = user_profile.email

        # Try to fetch the subscriber list as a non-member.
        stream_id = get_stream(stream_name, user_profile.realm).id
        result = self.make_subscriber_request(stream_id, email=other_email)
        self.assert_json_error(result, "Invalid stream id")

class AccessStreamTest(ZulipTestCase):
    def test_access_stream(self):
        # type: () -> None
        """
        A comprehensive security test for the access_stream_by_* API functions.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        hamlet = self.example_user('hamlet')
        hamlet_email = hamlet.email

        stream_name = "new_private_stream"
        self.login(hamlet_email)
        self.common_subscribe_to_streams(hamlet_email, [stream_name],
                                         invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        othello = self.example_user('othello')

        # Nobody can access a stream that doesn't exist
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(hamlet, 501232)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'invalid stream'"):
            access_stream_by_name(hamlet, "invalid stream")

        # Hamlet can access the private stream
        (stream_ret, rec_ret, sub_ret) = access_stream_by_id(hamlet, stream.id)
        self.assertEqual(stream, stream_ret)
        self.assertEqual(sub_ret.recipient, rec_ret)
        self.assertEqual(sub_ret.recipient.type_id, stream.id)
        (stream_ret2, rec_ret2, sub_ret2) = access_stream_by_name(hamlet, stream.name)
        self.assertEqual(stream_ret, stream_ret2)
        self.assertEqual(sub_ret, sub_ret2)
        self.assertEqual(rec_ret, rec_ret2)

        # Othello cannot access the private stream
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(othello, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'new_private_stream'"):
            access_stream_by_name(othello, stream.name)

        # Both Othello and Hamlet can access a public stream that only
        # Hamlet is subscribed to in this realm
        public_stream_name = "public_stream"
        self.common_subscribe_to_streams(hamlet_email, [public_stream_name],
                                         invite_only=False)
        public_stream = get_stream(public_stream_name, hamlet.realm)
        access_stream_by_id(othello, public_stream.id)
        access_stream_by_name(othello, public_stream.name)
        access_stream_by_id(hamlet, public_stream.id)
        access_stream_by_name(hamlet, public_stream.name)

        # Nobody can access a public stream in another realm
        mit_realm = get_realm("zephyr")
        mit_stream, _ = create_stream_if_needed(mit_realm, "mit_stream", invite_only=False)
        sipbtest = self.mit_user("sipbtest")
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(hamlet, mit_stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'mit_stream'"):
            access_stream_by_name(hamlet, mit_stream.name)
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(sipbtest, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'new_private_stream'"):
            access_stream_by_name(sipbtest, stream.name)

        # MIT realm users cannot access even public streams in their realm
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(sipbtest, mit_stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'mit_stream'"):
            access_stream_by_name(sipbtest, mit_stream.name)

        # But they can access streams they are subscribed to
        self.common_subscribe_to_streams(sipbtest.email, [mit_stream.name], subdomain="zephyr")
        access_stream_by_id(sipbtest, mit_stream.id)
        access_stream_by_name(sipbtest, mit_stream.name)
