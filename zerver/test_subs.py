# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib import cache

from zerver.lib.test_helpers import (
    AuthedTestCase, queries_captured, stub, tornado_redirected_to_list
)

from zerver.decorator import (
    JsonableError
)

from zerver.lib.test_runner import (
    slow
)

from zerver.models import (
    get_display_recipient, Message, Realm, Recipient, Stream, Subscription,
    UserProfile,
)

from zerver.lib.actions import (
    create_stream_if_needed, do_add_default_stream, do_add_subscription,
    do_change_is_admin, do_remove_default_stream, gather_subscriptions,
    get_default_streams_for_realm, get_realm, get_stream,
    get_user_profile_by_email, set_default_streams,
)

import random
import ujson
import urllib


class StreamAdminTest(AuthedTestCase):
    def test_make_stream_public(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'private_stream', invite_only=True)

        do_change_is_admin(user_profile, True)
        params = {
            'stream_name': 'private_stream'
        }
        result = self.client.post("/json/make_stream_public", params)
        self.assert_json_error(result, 'You are not invited to this stream.')

        do_add_subscription(user_profile, stream)

        do_change_is_admin(user_profile, True)
        params = {
            'stream_name': 'private_stream'
        }
        result = self.client.post("/json/make_stream_public", params)
        self.assert_json_success(result)
        stream = Stream.objects.get(name='private_stream', realm=realm)
        self.assertFalse(stream.invite_only)

    def test_make_stream_private(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'public_stream')

        do_change_is_admin(user_profile, True)
        params = {
            'stream_name': 'public_stream'
        }
        result = self.client.post("/json/make_stream_private", params)
        self.assert_json_success(result)
        stream = Stream.objects.get(name='public_stream', realm=realm)
        self.assertTrue(stream.invite_only)

    def test_deactivate_stream_backend(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'new_stream')
        do_add_subscription(user_profile, stream, no_log=True)
        do_change_is_admin(user_profile, True)

        result = self.client.delete('/json/streams/new_stream')
        self.assert_json_success(result)
        subscription_exists = Subscription.objects.filter(
            user_profile=user_profile,
            recipient__type_id=stream.id,
            recipient__type=Recipient.STREAM,
            active=True,
        ).exists()
        self.assertFalse(subscription_exists)

    def test_deactivate_stream_backend_requires_realm_admin(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'new_stream')
        do_add_subscription(user_profile, stream, no_log=True)

        result = self.client.delete('/json/streams/new_stream')
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_rename_stream(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'stream_name1')
        do_add_subscription(user_profile, stream, no_log=True)
        do_change_is_admin(user_profile, True)

        events = []
        with tornado_redirected_to_list(events):
            result = self.client.post('/json/rename_stream?old_name=stream_name1&new_name=stream_name2')
        self.assert_json_success(result)

        event = events[1]['event']
        self.assertEqual(event, dict(
            op='update',
            type='stream',
            property='name',
            value='stream_name2',
            name='stream_name1'
        ))
        users = events[1]['users']
        self.assertEqual(users, [user_profile.id])

        stream_name1_exists = Stream.objects.filter(
            name='stream_name1',
            realm=realm,
        ).exists()
        self.assertFalse(stream_name1_exists)
        stream_name2_exists = Stream.objects.filter(
            name='stream_name2',
            realm=realm,
        ).exists()
        self.assertTrue(stream_name2_exists)

    def test_rename_stream_requires_realm_admin(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'stream_name1')

        result = self.client.post('/json/rename_stream?old_name=stream_name1&new_name=stream_name2')
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_change_stream_description(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'stream_name1')
        do_add_subscription(user_profile, stream, no_log=True)
        do_change_is_admin(user_profile, True)

        events = []
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/streams/stream_name1',
                                      {'description': ujson.dumps('Test description')})
        self.assert_json_success(result)

        event = events[0]['event']
        self.assertEqual(event, dict(
            op='update',
            type='stream',
            property='description',
            value='Test description',
            name='stream_name1'
        ))
        users = events[0]['users']
        self.assertEqual(users, [user_profile.id])

        stream = Stream.objects.get(
            name='stream_name1',
            realm=realm,
        )
        self.assertEqual('Test description', stream.description)

    def test_change_stream_description_requires_realm_admin(self):
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)

        realm = user_profile.realm
        stream, _ = create_stream_if_needed(realm, 'stream_name1')
        do_add_subscription(user_profile, stream, no_log=True)
        do_change_is_admin(user_profile, False)

        result = self.client_patch('/json/streams/stream_name1',
                                  {'description': ujson.dumps('Test description')})
        self.assert_json_error(result, 'Must be a realm administrator')

    def set_up_stream_for_deletion(self, stream_name, invite_only=False,
                                   subscribed=True):
        """
        Create a stream for deletion by an administrator.
        """
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        stream, _ = create_stream_if_needed(user_profile.realm, stream_name,
                                            invite_only=invite_only)

        # For testing deleting streams you aren't on.
        if subscribed:
            do_add_subscription(user_profile, stream, no_log=True)

        do_change_is_admin(user_profile, True)

        return stream

    def delete_stream(self, stream, subscribed=True):
        """
        Delete the stream and assess the result.
        """
        active_name = stream.name

        events = []
        with tornado_redirected_to_list(events):
            result = self.client.delete('/json/streams/' + active_name)
        self.assert_json_success(result)

        deletion_events = [e['event'] for e in events if e['event']['type'] == 'subscription']
        if subscribed:
            self.assertEqual(deletion_events[0], dict(
                    op='remove',
                    type='subscription',
                    subscriptions=[{'name': active_name, 'stream_id': stream.id}]
                    ))
        else:
            # You could delete the stream, but you weren't on it so you don't
            # receive an unsubscription event.
            self.assertEqual(deletion_events, [])

        with self.assertRaises(Stream.DoesNotExist):
            Stream.objects.get(realm=get_realm("zulip.com"), name=active_name)

        # A deleted stream's name is changed, is deactivated, is invite-only,
        # and has no subscribers.
        deactivated_stream_name = "!DEACTIVATED:" + active_name
        deactivated_stream = Stream.objects.get(name=deactivated_stream_name)
        self.assertTrue(deactivated_stream.deactivated)
        self.assertTrue(deactivated_stream.invite_only)
        self.assertEqual(deactivated_stream.name, deactivated_stream_name)
        subscribers = self.users_subscribed_to_stream(
                deactivated_stream_name, "zulip.com")
        self.assertEqual(subscribers, [])

        # It doesn't show up in the list of public streams anymore.
        result = self.client.post("/json/get_public_streams")
        public_streams = [s["name"] for s in ujson.loads(result.content)["streams"]]
        self.assertNotIn(active_name, public_streams)
        self.assertNotIn(deactivated_stream_name, public_streams)

        # Even if you could guess the new name, you can't subscribe to it.
        result = self.client.post(
            "/json/subscriptions/add",
            {"subscriptions": ujson.dumps([{"name": deactivated_stream_name}])})
        self.assert_json_error(
            result, "Unable to access stream (%s)." % (deactivated_stream_name,))

    def test_delete_public_stream(self):
        """
        When an administrator deletes a public stream, that stream is not
        visible to users at all anymore.
        """
        stream = self.set_up_stream_for_deletion("newstream")
        self.delete_stream(stream)

    def test_delete_private_stream(self):
        """
        Administrators can delete private streams they are on.
        """
        stream = self.set_up_stream_for_deletion("newstream", invite_only=True)
        self.delete_stream(stream)

    def test_delete_streams_youre_not_on(self):
        """
        Administrators can delete public streams they aren't on, but cannot
        delete private streams they aren't on.
        """
        pub_stream = self.set_up_stream_for_deletion(
            "pubstream", subscribed=False)
        self.delete_stream(pub_stream, subscribed=False)

        priv_stream = self.set_up_stream_for_deletion(
            "privstream", subscribed=False, invite_only=True)

        result = self.client.delete('/json/streams/' + priv_stream.name)
        self.assert_json_error(
            result, "Cannot administer invite-only streams this way")

    def attempt_unsubscribe_of_principal(self, is_admin=False, is_subbed=True,
                                         invite_only=False, other_user_subbed=True):
        # Set up the main user, who is in most cases an admin.
        email = "hamlet@zulip.com"
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        realm = user_profile.realm
        if is_admin:
            do_change_is_admin(user_profile, True)

        # Set up the stream.
        stream_name = u"hümbüǵ"
        stream, _ = create_stream_if_needed(realm, stream_name,
                                            invite_only=invite_only)

        # Set up the principal to be unsubscribed.
        other_email = "cordelia@zulip.com"
        other_user_profile = get_user_profile_by_email(other_email)

        # Subscribe the admin and/or principal as specified in the flags.
        if is_subbed:
            do_add_subscription(user_profile, stream, no_log=True)
        if other_user_subbed:
            do_add_subscription(other_user_profile, stream, no_log=True)

        result = self.client.post(
            "/json/subscriptions/remove",
            {"subscriptions": ujson.dumps([stream.name]),
             "principals": ujson.dumps([other_email])})

        # If the removal succeeded, then assert that Cordelia is no longer subscribed.
        if result.status_code not in [400]:
            subbed_users = self.users_subscribed_to_stream(stream_name, other_user_profile.realm.domain)
            self.assertNotIn(other_user_profile, subbed_users)

        return result

    def test_cant_remove_others_from_stream(self):
        """
        If you're not an admin, you can't remove other people from streams.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=False, is_subbed=True, invite_only=False,
            other_user_subbed=True)
        self.assert_json_error(
            result, "This action requires administrative rights")

    def test_admin_remove_others_from_public_stream(self):
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
        """
        Even if you're an admin, you can't remove people from private
        streams you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            is_admin=True, is_subbed=False, invite_only=True,
            other_user_subbed=True)
        self.assert_json_error(
            result, "Cannot administer invite-only streams this way")

    def test_remove_already_not_subbed(self):
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
        """
        Trying to unsubscribe an invalid user from a stream fails gracefully.
        """
        admin_email = "hamlet@zulip.com"
        self.login(admin_email)
        user_profile = get_user_profile_by_email(admin_email)
        do_change_is_admin(user_profile, True)
        realm = user_profile.realm

        stream_name = u"hümbüǵ"
        stream, _ = create_stream_if_needed(realm, stream_name)

        result = self.client.post("/json/subscriptions/remove",
                                  {"subscriptions": ujson.dumps([stream.name]),
                                   "principals": ujson.dumps(["baduser@zulip.com"])})
        self.assert_json_error(
            result,
            "User not authorized to execute queries on behalf of 'baduser@zulip.com'")

class DefaultStreamTest(AuthedTestCase):
    def get_default_stream_names(self, realm):
        streams = get_default_streams_for_realm(realm)
        stream_names = [s.name for s in streams]
        return set(stream_names)

    def test_set_default_streams(self):
        realm = Realm.objects.get(domain="zulip.com")
        stream_names = ['apple', 'banana', 'Carrot Cake']
        expected_names = stream_names + ['zulip']
        set_default_streams(realm, stream_names)
        stream_names = self.get_default_stream_names(realm)
        self.assertEqual(stream_names, set(expected_names))

    def test_add_and_remove_default_stream(self):
        realm = Realm.objects.get(domain="zulip.com")
        orig_stream_names = self.get_default_stream_names(realm)
        do_add_default_stream(realm, 'Added Stream')
        new_stream_names = self.get_default_stream_names(realm)
        added_stream_names = new_stream_names - orig_stream_names
        self.assertEqual(added_stream_names, set(['Added Stream']))
        # idempotentcy--2nd call to add_default_stream should be a noop
        do_add_default_stream(realm, 'Added Stream')
        self.assertEqual(self.get_default_stream_names(realm), new_stream_names)

        # start removing
        do_remove_default_stream(realm, 'Added Stream')
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)
        # idempotentcy--2nd call to remove_default_stream should be a noop
        do_remove_default_stream(realm, 'Added Stream')
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)

    def test_api_calls(self):
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        do_change_is_admin(user_profile, True)
        stream_name = 'stream ADDED via api'
        result = self.client_patch('/json/default_streams', dict(stream_name=stream_name))
        self.assert_json_success(result)
        self.assertTrue(stream_name in self.get_default_stream_names(user_profile.realm))

        # and remove it
        result = self.client_delete('/json/default_streams', dict(stream_name=stream_name))
        self.assert_json_success(result)
        self.assertFalse(stream_name in self.get_default_stream_names(user_profile.realm))

class SubscriptionPropertiesTest(AuthedTestCase):
    def test_set_stream_color(self):
        """
        A POST request to /json/subscriptions/property with stream_name and
        color data sets the stream color, and for that stream only.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)

        old_subs, _ = gather_subscriptions(get_user_profile_by_email(test_email))
        sub = old_subs[0]
        stream_name = sub['name']
        new_color = "#ffffff" # TODO: ensure that this is different from old_color
        result = self.client.post(
            "/json/subscriptions/property",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "stream": stream_name,
                                                "value": "#ffffff"}])})

        self.assert_json_success(result)

        new_subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        found_sub = None
        for sub in new_subs:
            if sub['name'] == stream_name:
                found_sub = sub
                break

        self.assertIsNotNone(found_sub)
        self.assertEqual(found_sub['color'], new_color)

        new_subs.remove(found_sub)
        for sub in old_subs:
            if sub['name'] == stream_name:
                found_sub = sub
                break
        old_subs.remove(found_sub)
        self.assertEqual(old_subs, new_subs)

    def test_set_color_missing_stream_name(self):
        """
        Updating the color property requires a `stream` key.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        result = self.client.post(
            "/json/subscriptions/property",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "value": "#ffffff"}])})

        self.assert_json_error(
            result, "stream key is missing from subscription_data[0]")

    def test_set_color_missing_color(self):
        """
        Updating the color property requires a color.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        result = self.client.post(
            "/json/subscriptions/property",
            {"subscription_data": ujson.dumps([{"property": "color",
                                                "stream": subs[0]["name"]}])})

        self.assert_json_error(
            result, "value key is missing from subscription_data[0]")

    def test_set_invalid_property(self):
        """
        Trying to set an invalid property returns a JSON error.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        result = self.client.post(
            "/json/subscriptions/property",
            {"subscription_data": ujson.dumps([{"property": "bad",
                                                "value": "bad",
                                                "stream": subs[0]["name"]}])})

        self.assert_json_error(result,
                               "Unknown subscription property: bad")

class SubscriptionRestApiTest(AuthedTestCase):
    def test_basic_add_delete(self):
        email = 'hamlet@zulip.com'
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
        streams = self.get_streams(email)
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
        streams = self.get_streams(email)
        self.assertTrue('my_test_stream_1' not in streams)

    def test_bad_add_parameters(self):
        email = 'hamlet@zulip.com'
        self.login(email)

        def check_for_error(val, expected_message):
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
        email = 'hamlet@zulip.com'
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
        email = 'hamlet@zulip.com'
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

class SubscriptionAPITest(AuthedTestCase):

    def setUp(self):
        """
        All tests will be logged in as hamlet. Also save various useful values
        as attributes that tests can access.
        """
        self.test_email = "hamlet@zulip.com"
        self.login(self.test_email)
        self.user_profile = get_user_profile_by_email(self.test_email)
        self.realm = self.user_profile.realm
        self.streams = self.get_streams(self.test_email)

    def make_random_stream_names(self, existing_stream_names):
        """
        Helper function to make up random stream names. It takes
        existing_stream_names and randomly appends a digit to the end of each,
        but avoids names that appear in the list names_to_avoid.
        """
        random_streams = []
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.realm)]
        for stream in existing_stream_names:
            random_stream = stream + str(random.randint(0, 9))
            if not random_stream in all_stream_names:
                random_streams.append(random_stream)
        return random_streams

    def test_successful_subscriptions_list(self):
        """
        Calling /api/v1/users/me/subscriptions should successfully return your subscriptions.
        """
        email = self.test_email
        result = self.client.get("/api/v1/users/me/subscriptions", **self.api_auth(email))
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("subscriptions", json)
        for stream in json['subscriptions']:
            self.assertIsInstance(stream['name'], basestring)
            self.assertIsInstance(stream['color'], basestring)
            self.assertIsInstance(stream['invite_only'], bool)
            # check that the stream name corresponds to an actual stream
            try:
                Stream.objects.get(name__iexact=stream['name'], realm=self.realm)
            except Stream.DoesNotExist:
                self.fail("stream does not exist")
        list_streams = [stream['name'] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertItemsEqual(list_streams, self.streams)

    def helper_check_subs_before_and_after_add(self, subscriptions, other_params,
                                               subscribed, already_subscribed,
                                               email, new_subs, invite_only=False):
        """
        Check result of adding subscriptions.

        You can add subscriptions for yourself or possibly many
        principals, which is why e-mails map to subscriptions in the
        result.

        The result json is of the form

        {"msg": "",
         "result": "success",
         "already_subscribed": {"iago@zulip.com": ["Venice", "Verona"]},
         "subscribed": {"iago@zulip.com": ["Venice8"]}}
        """
        result = self.common_subscribe_to_streams(self.test_email, subscriptions,
                                                  other_params, invite_only=invite_only)
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertItemsEqual(subscribed, json["subscribed"][email])
        self.assertItemsEqual(already_subscribed, json["already_subscribed"][email])
        new_streams = self.get_streams(email)
        self.assertItemsEqual(new_streams, new_subs)

    def test_successful_subscriptions_add(self):
        """
        Calling /json/subscriptions/add should successfully add streams, and
        should determine which are new subscriptions vs which were already
        subscribed. We randomly generate stream names to add, because it
        doesn't matter whether the stream already exists.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        add_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(add_streams), 0)  # necessary for full test coverage
        events = []
        with tornado_redirected_to_list(events):
            self.helper_check_subs_before_and_after_add(self.streams + add_streams, {},
                add_streams, self.streams, self.test_email, self.streams + add_streams)
        self.assert_length(events, 4, True)

    def test_successful_subscriptions_notifies_pm(self):
        """
        Calling /json/subscriptions/add should notify when a new stream is created.
        """
        invitee = "iago@zulip.com"
        invitee_full_name = 'Iago'

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names(current_stream)[:1]
        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data={
                'announce': 'true',
                'principals': '["%s"]' % (self.user_profile.email,)
            },
        )
        self.assert_json_success(result)

        msg = Message.objects.latest('id')
        self.assertEqual(msg.recipient.type, Recipient.PERSONAL)
        self.assertEqual(msg.sender_id,
                         get_user_profile_by_email('notification-bot@zulip.com').id)
        expected_msg = "Hi there!  %s just created a new stream '%s'. " \
                       "!_stream_subscribe_button(%s)" % (invitee_full_name,
                                                          invite_streams[0],
                                                          invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_successful_subscriptions_notifies_stream(self):
        """
        Calling /json/subscriptions/add should notify when a new stream is created.
        """
        invitee = "iago@zulip.com"
        invitee_full_name = 'Iago'

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names(current_stream)[:1]

        notifications_stream = Stream.objects.get(name=current_stream, realm=self.realm)
        self.realm.notifications_stream = notifications_stream
        self.realm.save()

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

        msg = Message.objects.latest('id')
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.sender_id,
                         get_user_profile_by_email('notification-bot@zulip.com').id)
        expected_msg = "%s just created a new stream `%s`. " \
                       "!_stream_subscribe_button(%s)" % (invitee_full_name,
                                                          invite_streams[0],
                                                          invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_successful_subscriptions_notifies_with_escaping(self):
        """
        Calling /json/subscriptions/add should notify when a new stream is created.
        """
        invitee = "iago@zulip.com"
        invitee_full_name = 'Iago'

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

        msg = Message.objects.latest('id')
        self.assertEqual(msg.sender_id,
                         get_user_profile_by_email('notification-bot@zulip.com').id)
        expected_msg = "Hi there!  %s just created a new stream '%s'. " \
                       "!_stream_subscribe_button(strange \\) \\\\ test)" % (
                                                          invitee_full_name,
                                                          invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_non_ascii_stream_subscription(self):
        """
        Subscribing to a stream name with non-ASCII characters succeeds.
        """
        self.helper_check_subs_before_and_after_add(self.streams + [u"hümbüǵ"], {},
            [u"hümbüǵ"], self.streams, self.test_email, self.streams + [u"hümbüǵ"])

    def test_subscriptions_add_too_long(self):
        """
        Calling /json/subscriptions/add on a stream whose name is >60
        characters should return a JSON error.
        """
        # character limit is 60 characters
        long_stream_name = "a" * 61
        result = self.common_subscribe_to_streams(self.test_email, [long_stream_name])
        self.assert_json_error(result,
                               "Stream name (%s) too long." % (long_stream_name,))

    def test_user_settings_for_adding_streams(self):
        with stub(UserProfile, 'can_create_streams', lambda self: True):
            result = self.common_subscribe_to_streams(self.test_email, ['stream1'])
            self.assert_json_success(result)

        with stub(UserProfile, 'can_create_streams', lambda self: False):
            result = self.common_subscribe_to_streams(self.test_email, ['stream1'])
            self.assert_json_error(result, 'User cannot create streams.')

    def test_subscriptions_add_invalid_stream(self):
        """
        Calling /json/subscriptions/add on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid name is the empty string
        invalid_stream_name = ""
        result = self.common_subscribe_to_streams(self.test_email, [invalid_stream_name])
        self.assert_json_error(result,
                               "Invalid stream name (%s)." % (invalid_stream_name,))

    def assert_adding_subscriptions_for_principal(self, invitee, streams, invite_only=False):
        """
        Calling /json/subscriptions/add on behalf of another principal (for
        whom you have permission to add subscriptions) should successfully add
        those subscriptions and send a message to the subscribee notifying
        them.
        """
        other_profile = get_user_profile_by_email(invitee)
        current_streams = self.get_streams(invitee)
        self.assertIsInstance(other_profile, UserProfile)
        self.assertNotEqual(len(current_streams), 0)  # necessary for full test coverage
        self.assertNotEqual(len(streams), 0)  # necessary for full test coverage
        streams_to_sub = streams[:1]  # just add one, to make the message easier to check
        streams_to_sub.extend(current_streams)
        self.helper_check_subs_before_and_after_add(streams_to_sub,
            {"principals": ujson.dumps([invitee])}, streams[:1], current_streams,
            invitee, streams_to_sub, invite_only=invite_only)
        # verify that the user was sent a message informing them about the subscription
        msg = Message.objects.latest('id')
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id,
                get_user_profile_by_email("notification-bot@zulip.com").id)
        expected_msg = ("Hi there!  We thought you'd like to know that %s just "
                        "subscribed you to the %sstream [%s](#narrow/stream/%s)."
                        % (self.user_profile.full_name,
                           '**invite-only** ' if invite_only else '',
                           streams[0], urllib.quote(streams[0].encode('utf-8'))))

        if not Stream.objects.get(name=streams[0]).invite_only:
            expected_msg += ("\nYou can see historical content on a "
                             "non-invite-only stream by narrowing to it.")
        self.assertEqual(msg.content, expected_msg)
        recipients = get_display_recipient(msg.recipient)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['email'], invitee)

    def test_multi_user_subscription(self):
        email1 = 'cordelia@zulip.com'
        email2 = 'iago@zulip.com'
        realm = Realm.objects.get(domain="zulip.com")
        streams_to_sub = ['multi_user_stream']
        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_email,
                    streams_to_sub,
                    dict(principals=ujson.dumps([email1, email2])),
            )
        self.assert_length(queries, 43)

        self.assert_length(events, 6, exact=True)
        for ev in filter(lambda x: x['event']['type'] not in ('message', 'stream'), events):
            self.assertEqual(ev['event']['op'], 'add')
            self.assertEqual(
                    set(ev['event']['subscriptions'][0]['subscribers']),
                    set([email1, email2])
            )

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
        self.assert_length(queries, 8)

        self.assert_length(events, 2, True)
        add_event, add_peer_event = events
        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user_profile_by_email(self.test_email).id])
        self.assertEqual(
                set(add_event['event']['subscriptions'][0]['subscribers']),
                set([email1, email2, self.test_email])
        )

        self.assertEqual(len(add_peer_event['users']), 2)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_email'], self.test_email)

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(stream.num_subscribers(), 3)

        # Finally, add othello, exercising the do_add_subscription() code path.
        events = []
        email3 = 'othello@zulip.com'
        user_profile = get_user_profile_by_email(email3)
        stream = get_stream('multi_user_stream', realm)
        with tornado_redirected_to_list(events):
            do_add_subscription(user_profile, stream)

        self.assert_length(events, 2, True)
        add_event, add_peer_event = events

        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user_profile_by_email(email3).id])
        self.assertEqual(
                set(add_event['event']['subscriptions'][0]['subscribers']),
                set([email1, email2, email3, self.test_email])
        )

        self.assertEqual(len(add_peer_event['users']), 3)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_email'], email3)


    def test_bulk_subscribe_MIT(self):
        realm = Realm.objects.get(domain="mit.edu")
        streams = ["stream_%s" % i for i in xrange(40)]
        for stream in streams:
            create_stream_if_needed(realm, stream)

        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                        'starnine@mit.edu',
                        streams,
                        dict(principals=ujson.dumps(['starnine@mit.edu'])),
                )
        # Make sure MIT does not get any tornado subscription events
        self.assert_length(events, 0, True)
        self.assert_length(queries, 7)

    def test_bulk_subscribe_many(self):
        # Create a whole bunch of streams
        realm = Realm.objects.get(domain="zulip.com")
        streams = ["stream_%s" % i for i in xrange(20)]
        for stream in streams:
            create_stream_if_needed(realm, stream)

        with queries_captured() as queries:
                self.common_subscribe_to_streams(
                        self.test_email,
                        streams,
                        dict(principals=ujson.dumps([self.test_email])),
                )
        # Make sure we don't make O(streams) queries
        self.assert_length(queries, 9)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_subscriptions_add_for_principal(self):
        """
        You can subscribe other people to streams.
        """
        invitee = "iago@zulip.com"
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_subscriptions_add_for_principal_invite_only(self):
        """
        You can subscribe other people to invite only streams.
        """
        invitee = "iago@zulip.com"
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams,
                                                       invite_only=True)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_non_ascii_subscription_for_principal(self):
        """
        You can subscribe other people to streams even if they containing
        non-ASCII characters.
        """
        self.assert_adding_subscriptions_for_principal("iago@zulip.com", [u"hümbüǵ"])

    def test_subscription_add_invalid_principal(self):
        """
        Calling subscribe on behalf of a principal that does not exist
        should return a JSON error.
        """
        invalid_principal = "rosencrantz-and-guildenstern@zulip.com"
        # verify that invalid_principal actually doesn't exist
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_profile_by_email(invalid_principal)
        result = self.common_subscribe_to_streams(self.test_email, self.streams,
                                                  {"principals": ujson.dumps([invalid_principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (invalid_principal,))

    def test_subscription_add_principal_other_realm(self):
        """
        Calling subscribe on behalf of a principal in another realm
        should return a JSON error.
        """
        principal = "starnine@mit.edu"
        profile = get_user_profile_by_email(principal)
        # verify that principal exists (thus, the reason for the error is the cross-realming)
        self.assertIsInstance(profile, UserProfile)
        result = self.common_subscribe_to_streams(self.test_email, self.streams,
                                                  {"principals": ujson.dumps([principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (principal,))

    def helper_check_subs_before_and_after_remove(self, subscriptions, json_dict,
                                                  email, new_subs):
        """
        Check result of removing subscriptions.

        Unlike adding subscriptions, you can only remove subscriptions
        for yourself, so the result format is different.

        {"msg": "",
         "removed": ["Denmark", "Scotland", "Verona"],
         "not_subscribed": ["Rome"], "result": "success"}
        """
        result = self.client.post("/json/subscriptions/remove",
                                  {"subscriptions": ujson.dumps(subscriptions)})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        for key, val in json_dict.iteritems():
            self.assertItemsEqual(val, json[key])  # we don't care about the order of the items
        new_streams = self.get_streams(email)
        self.assertItemsEqual(new_streams, new_subs)

    def test_successful_subscriptions_remove(self):
        """
        Calling /json/subscriptions/remove should successfully remove streams,
        and should determine which were removed vs which weren't subscribed to.
        We cannot randomly generate stream names because the remove code
        verifies whether streams exist.
        """
        if len(self.streams) < 2:
            self.fail()  # necesssary for full test coverage
        streams_to_remove = self.streams[1:]
        not_subbed = []
        for stream in Stream.objects.all():
            if not stream.name in self.streams:
                not_subbed.append(stream.name)
        random.shuffle(not_subbed)
        self.assertNotEqual(len(not_subbed), 0)  # necessary for full test coverage
        try_to_remove = not_subbed[:3]  # attempt to remove up to 3 streams not already subbed to
        streams_to_remove.extend(try_to_remove)
        self.helper_check_subs_before_and_after_remove(streams_to_remove,
            {"removed": self.streams[1:], "not_subscribed": try_to_remove},
            self.test_email, [self.streams[0]])

    def test_subscriptions_remove_fake_stream(self):
        """
        Calling /json/subscriptions/remove on a stream that doesn't exist
        should return a JSON error.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        streams_to_remove = random_streams[:1]  # pick only one fake stream, to make checking the error message easy
        result = self.client.post("/json/subscriptions/remove",
                                  {"subscriptions": ujson.dumps(streams_to_remove)})
        self.assert_json_error(result, "Stream(s) (%s) do not exist" % (random_streams[0],))

    def helper_subscriptions_exists(self, stream, exists, subscribed):
        """
        A helper function that calls /json/subscriptions/exists on a stream and
        verifies that the returned JSON dictionary has the exists and
        subscribed values passed in as parameters. (If subscribed should not be
        present, pass in None.)
        """
        result = self.client.post("/json/subscriptions/exists",
                                  {"stream": stream})
        json = ujson.loads(result.content)
        self.assertIn("exists", json)
        self.assertEqual(json["exists"], exists)
        if exists:
            self.assert_json_success(result)
        else:
            self.assertEquals(result.status_code, 404)
        if not subscribed is None:
            self.assertIn("subscribed", json)
            self.assertEqual(json["subscribed"], subscribed)

    def test_successful_subscriptions_exists_subbed(self):
        """
        Calling /json/subscriptions/exist on a stream to which you are subbed
        should return that it exists and that you are subbed.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(self.streams[0], True, True)

    def test_successful_subscriptions_exists_not_subbed(self):
        """
        Calling /json/subscriptions/exist on a stream to which you are not
        subbed should return that it exists and that you are not subbed.
        """
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.realm)]
        streams_not_subbed = list(set(all_stream_names) - set(self.streams))
        self.assertNotEqual(len(streams_not_subbed), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(streams_not_subbed[0], True, False)

    def test_subscriptions_does_not_exist(self):
        """
        Calling /json/subscriptions/exist on a stream that doesn't exist should
        return that it doesn't exist.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(random_streams[0], False, None)

    def test_subscriptions_exist_invalid_name(self):
        """
        Calling /json/subscriptions/exist on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid stream name is the empty string
        invalid_stream_name = ""
        result = self.client.post("/json/subscriptions/exists",
                                  {"stream": invalid_stream_name})
        self.assert_json_error(result, "Invalid characters in stream name")

    def get_subscription(self, user_profile, stream_name):
        stream = Stream.objects.get(realm=self.realm, name=stream_name)
        return Subscription.objects.get(
            user_profile=user_profile,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id,
        )

    def test_subscriptions_add_notification_default_true(self):
        """
        When creating a subscription, the desktop and audible notification
        settings for that stream are derived from the global notification
        settings.
        """
        invitee = "iago@zulip.com"
        user_profile = get_user_profile_by_email(invitee)
        user_profile.enable_stream_desktop_notifications = True
        user_profile.enable_stream_sounds = True
        user_profile.save()
        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names(current_stream)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams)
        subscription = self.get_subscription(user_profile, invite_streams[0])
        self.assertTrue(subscription.desktop_notifications)
        self.assertTrue(subscription.audible_notifications)

    def test_subscriptions_add_notification_default_false(self):
        """
        When creating a subscription, the desktop and audible notification
        settings for that stream are derived from the global notification
        settings.
        """
        invitee = "iago@zulip.com"
        user_profile = get_user_profile_by_email(invitee)
        user_profile.enable_stream_desktop_notifications = False
        user_profile.enable_stream_sounds = False
        user_profile.save()
        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names(current_stream)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams)
        subscription = self.get_subscription(user_profile, invite_streams[0])
        self.assertFalse(subscription.desktop_notifications)
        self.assertFalse(subscription.audible_notifications)


class GetPublicStreamsTest(AuthedTestCase):

    def test_public_streams(self):
        """
        Ensure that get_public_streams successfully returns a list of streams
        """
        email = 'hamlet@zulip.com'
        self.login(email)

        result = self.client.post("/json/get_public_streams")

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

    def test_public_streams_api(self):
        """
        Ensure that get_public_streams successfully returns a list of streams
        """
        email = 'hamlet@zulip.com'
        self.login(email)

        # Check it correctly lists the user's subs with include_public=false
        result = self.client.get("/api/v1/streams?include_public=false", **self.api_auth(email))
        result2 = self.client.get("/api/v1/users/me/subscriptions", **self.api_auth(email))

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("streams", json)

        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(result2)
        json2 = ujson.loads(result2.content)

        self.assertEqual(sorted([s["name"] for s in json["streams"]]),
                         sorted([s["name"] for s in json2["subscriptions"]]))

        # Check it correctly lists all public streams with include_subscribed=false
        result = self.client.get("/api/v1/streams?include_public=true&include_subscribed=false",
                                 **self.api_auth(email))
        self.assert_json_success(result)

        json = ujson.loads(result.content)
        all_streams = [stream.name for stream in
                       Stream.objects.filter(realm=get_user_profile_by_email(email).realm)]
        self.assertEqual(sorted(s["name"] for s in json["streams"]),
                         sorted(all_streams))

        # Check non-superuser can't use include_all_active
        result = self.client.get("/api/v1/streams?include_all_active=true",
                                 **self.api_auth(email))
        self.assertEqual(result.status_code, 400)

class InviteOnlyStreamTest(AuthedTestCase):
    def test_must_be_subbed_to_send(self):
        """
        If you try to send a message to an invite-only stream to which
        you aren't subscribed, you'll get a 400.
        """
        self.login("hamlet@zulip.com")
        # Create Saxony as an invite-only stream.
        self.assert_json_success(
            self.common_subscribe_to_streams("hamlet@zulip.com", ["Saxony"],
                                             invite_only=True))

        email = "cordelia@zulip.com"
        with self.assertRaises(JsonableError):
            self.send_message(email, "Saxony", Recipient.STREAM)

    def test_list_respects_invite_only_bit(self):
        """
        Make sure that /api/v1/users/me/subscriptions properly returns
        the invite-only bit for streams that are invite-only
        """
        email = 'hamlet@zulip.com'
        self.login(email)

        result1 = self.common_subscribe_to_streams(email, ["Saxony"], invite_only=True)
        self.assert_json_success(result1)
        result2 = self.common_subscribe_to_streams(email, ["Normandy"], invite_only=False)
        self.assert_json_success(result2)
        result = self.client.get("/api/v1/users/me/subscriptions", **self.api_auth(email))
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("subscriptions", json)
        for sub in json["subscriptions"]:
            if sub['name'] == "Normandy":
                self.assertEqual(sub['invite_only'], False, "Normandy was mistakenly marked invite-only")
            if sub['name'] == "Saxony":
                self.assertEqual(sub['invite_only'], True, "Saxony was not properly marked invite-only")

    @slow(0.15, "lots of queries")
    def test_inviteonly(self):
        # Creating an invite-only stream is allowed
        email = 'hamlet@zulip.com'
        stream_name = "Saxony"

        result = self.common_subscribe_to_streams(email, [stream_name], invite_only=True)
        self.assert_json_success(result)

        json = ujson.loads(result.content)
        self.assertEqual(json["subscribed"], {email: [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is not allowed
        email = "othello@zulip.com"
        self.login(email)
        result = self.common_subscribe_to_streams(email, [stream_name])
        self.assert_json_error(result, 'Unable to access stream (Saxony).')

        # authorization_errors_fatal=False works
        email = "othello@zulip.com"
        self.login(email)
        result = self.common_subscribe_to_streams(email, [stream_name],
                                                  extra_post_data={'authorization_errors_fatal': ujson.dumps(False)})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json["unauthorized"], [stream_name])
        self.assertEqual(json["subscribed"], {})
        self.assertEqual(json["already_subscribed"], {})

        # Inviting another user to an invite-only stream is allowed
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self.common_subscribe_to_streams(
            email, [stream_name],
            extra_post_data={'principals': ujson.dumps(["othello@zulip.com"])})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json["subscribed"], {"othello@zulip.com": [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Make sure both users are subscribed to this stream
        result = self.client.get("/api/v1/streams/%s/members" % (stream_name,),
                                 **self.api_auth(email))
        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertTrue('othello@zulip.com' in json['subscribers'])
        self.assertTrue('hamlet@zulip.com' in json['subscribers'])

class GetSubscribersTest(AuthedTestCase):

    def setUp(self):
        self.email = "hamlet@zulip.com"
        self.user_profile = get_user_profile_by_email(self.email)
        self.login(self.email)

    def check_well_formed_result(self, result, stream_name, domain):
        """
        A successful call to get_subscribers returns the list of subscribers in
        the form:

        {"msg": "",
         "result": "success",
         "subscribers": ["hamlet@zulip.com", "prospero@zulip.com"]}
        """
        self.assertIn("subscribers", result)
        self.assertIsInstance(result["subscribers"], list)
        true_subscribers = [user_profile.email for user_profile in self.users_subscribed_to_stream(
                stream_name, domain)]
        self.assertItemsEqual(result["subscribers"], true_subscribers)

    def make_subscriber_request(self, stream_name, email=None):
        if email is None:
            email = self.email
        return self.client.get("/api/v1/streams/%s/members" % (stream_name,),
                               **self.api_auth(email))

    def make_successful_subscriber_request(self, stream_name):
        result = self.make_subscriber_request(stream_name)
        self.assert_json_success(result)
        self.check_well_formed_result(ujson.loads(result.content),
                                      stream_name, self.user_profile.realm.domain)

    def test_subscriber(self):
        """
        get_subscribers returns the list of subscribers.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]['name']
        self.make_successful_subscriber_request(stream_name)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_gather_subscriptions(self):
        """
        gather_subscriptions returns correct results with only 3 queries
        """
        realm = Realm.objects.get(domain="zulip.com")
        streams = ["stream_%s" % i for i in xrange(10)]
        for stream in streams:
            create_stream_if_needed(realm, stream)
        users_to_subscribe = [self.email, "othello@zulip.com", "cordelia@zulip.com"]
        ret = self.common_subscribe_to_streams(
            self.email,
            streams,
            dict(principals=ujson.dumps(users_to_subscribe)))
        self.assert_json_success(ret)
        ret = self.common_subscribe_to_streams(
            self.email,
            ["stream_invite_only_1"],
            dict(principals=ujson.dumps(users_to_subscribe)),
            invite_only=True)
        self.assert_json_success(ret)

        with queries_captured() as queries:
            subscriptions = gather_subscriptions(self.user_profile)
        self.assertTrue(len(subscriptions[0]) >= 11)
        for sub in subscriptions[0]:
            if not sub["name"].startswith("stream_"):
                continue
            self.assertTrue(len(sub["subscribers"]) == len(users_to_subscribe))
        self.assert_length(queries, 4, exact=True)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_gather_subscriptions_mit(self):
        """
        gather_subscriptions returns correct results with only 3 queries
        """
        # Subscribe only ourself because invites are disabled on mit.edu
        users_to_subscribe = ["starnine@mit.edu", "espuser@mit.edu"]
        for email in users_to_subscribe:
            self.subscribe_to_stream(email, "mit_stream")

        ret = self.common_subscribe_to_streams(
            "starnine@mit.edu",
            ["mit_invite_only"],
            dict(principals=ujson.dumps(users_to_subscribe)),
            invite_only=True)
        self.assert_json_success(ret)

        with queries_captured() as queries:
            subscriptions = gather_subscriptions(get_user_profile_by_email("starnine@mit.edu"))

        self.assertTrue(len(subscriptions[0]) >= 2)
        for sub in subscriptions[0]:
            if not sub["name"].startswith("mit_"):
                continue
            if sub["name"] == "mit_invite_only":
                self.assertTrue(len(sub["subscribers"]) == len(users_to_subscribe))
            else:
                self.assertTrue(len(sub["subscribers"]) == 0)
        self.assert_length(queries, 4, exact=True)

    def test_nonsubscriber(self):
        """
        Even a non-subscriber to a public stream can query a stream's membership
        with get_subscribers.
        """
        # Create a stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name])
        other_email = "othello@zulip.com"

        # Fetch the subscriber list as a non-member.
        self.login(other_email)
        self.make_successful_subscriber_request(stream_name)

    def test_subscriber_private_stream(self):
        """
        A subscriber to a private stream can query that stream's membership.
        """
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name],
                                         invite_only=True)
        self.make_successful_subscriber_request(stream_name)

    def test_nonsubscriber_private_stream(self):
        """
        A non-subscriber to a private stream can't query that stream's membership.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        stream_name = "NewStream"
        self.common_subscribe_to_streams(self.email, [stream_name],
                                         invite_only=True)
        other_email = "othello@zulip.com"

        # Try to fetch the subscriber list as a non-member.
        result = self.make_subscriber_request(stream_name, email=other_email)
        self.assert_json_error(result,
                               "Unable to retrieve subscribers for invite-only stream")

