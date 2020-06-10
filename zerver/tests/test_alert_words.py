import ujson

from zerver.lib.actions import do_add_alert_words, do_remove_alert_words
from zerver.lib.alert_words import alert_words_in_realm, user_alert_words
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message, most_recent_usermessage
from zerver.models import UserProfile


class AlertWordTests(ZulipTestCase):
    interesting_alert_word_list = ['alert', 'multi-word word', '☃']

    def test_internal_endpoint(self) -> None:
        user_name = "cordelia"
        self.login(user_name)

        params = {
            'alert_words': ujson.dumps(['milk', 'cookies']),
        }
        result = self.client_post('/json/users/me/alert_words', params)
        self.assert_json_success(result)
        user = self.example_user(user_name)
        words = user_alert_words(user)
        self.assertEqual(set(words), {'milk', 'cookies'})

    def test_default_no_words(self) -> None:
        """
        Users start out with no alert words.
        """
        user = self.example_user('cordelia')
        words = user_alert_words(user)
        self.assertEqual(words, [])

    def test_basics(self) -> None:
        """
        Verifies the basic behavior of modifying alert words.

        Also verifies the cache-flushing behavior.
        """
        user = self.example_user('cordelia')
        realm_alert_words = alert_words_in_realm(user.realm)
        self.assert_length(realm_alert_words.get(user.id, []), 0)

        # Add several words, including multi-word and non-ascii words.
        do_add_alert_words(user, self.interesting_alert_word_list)

        words = user_alert_words(user)
        self.assertEqual(set(words), set(self.interesting_alert_word_list))
        realm_alert_words = alert_words_in_realm(user.realm)
        self.assert_length(realm_alert_words[user.id], 3)

        # Test the case-insensitivity of adding words
        do_add_alert_words(user, {"ALert", "ALERT"})
        words = user_alert_words(user)
        self.assertEqual(set(words), set(self.interesting_alert_word_list))
        realm_alert_words = alert_words_in_realm(user.realm)
        self.assert_length(realm_alert_words[user.id], 3)

        # Test the case-insensitivity of removing words
        do_remove_alert_words(user, {"ALert"})
        words = user_alert_words(user)
        self.assertEqual(set(words), set(self.interesting_alert_word_list) - {'alert'})
        realm_alert_words = alert_words_in_realm(user.realm)
        self.assert_length(realm_alert_words[user.id], 2)

    def test_remove_word(self) -> None:
        """
        Removing alert words works via do_remove_alert_words, even
        for multi-word and non-ascii words.
        """
        user = self.example_user('cordelia')

        expected_remaining_alerts = set(self.interesting_alert_word_list)
        do_add_alert_words(user, self.interesting_alert_word_list)

        for alert_word in self.interesting_alert_word_list:
            do_remove_alert_words(user, [alert_word])
            expected_remaining_alerts.remove(alert_word)
            actual_remaining_alerts = user_alert_words(user)
            self.assertEqual(set(actual_remaining_alerts),
                             expected_remaining_alerts)

    def test_realm_words(self) -> None:
        """
        We can gather alert words for an entire realm via
        alert_words_in_realm. Alerts added for one user do not impact other
        users.
        """
        user1 = self.example_user('cordelia')

        do_add_alert_words(user1, self.interesting_alert_word_list)

        user2 = self.example_user('othello')
        do_add_alert_words(user2, ['another'])

        realm_words = alert_words_in_realm(user2.realm)
        self.assertEqual(len(realm_words), 2)
        self.assertEqual(set(realm_words.keys()), {user1.id, user2.id})
        self.assertEqual(set(realm_words[user1.id]),
                         set(self.interesting_alert_word_list))
        self.assertEqual(set(realm_words[user2.id]), {'another'})

    def test_json_list_default(self) -> None:
        self.login('hamlet')

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        self.assertEqual(result.json()['alert_words'], [])

    def test_json_list_nonempty(self) -> None:
        hamlet = self.example_user('hamlet')
        do_add_alert_words(hamlet, ['one', 'two', 'three'])

        self.login('hamlet')
        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        self.assertEqual(set(result.json()['alert_words']), {'one', 'two', 'three'})

    def test_json_list_add(self) -> None:
        self.login('hamlet')

        result = self.client_post('/json/users/me/alert_words',
                                  {'alert_words': ujson.dumps(['one ', '\n two', 'three'])})
        self.assert_json_success(result)
        self.assertEqual(set(result.json()['alert_words']), {'one', 'two', 'three'})

    def test_json_list_remove(self) -> None:
        self.login('hamlet')

        result = self.client_post('/json/users/me/alert_words',
                                  {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)
        self.assertEqual(set(result.json()['alert_words']), {'one', 'two', 'three'})

        result = self.client_delete('/json/users/me/alert_words',
                                    {'alert_words': ujson.dumps(['one'])})
        self.assert_json_success(result)
        self.assertEqual(set(result.json()['alert_words']), {'two', 'three'})

    def message_does_alert(self, user_profile: UserProfile, message: str) -> bool:
        """Send a bunch of messages as othello, so Hamlet is notified"""
        self.send_stream_message(self.example_user("othello"), "Denmark", message)
        user_message = most_recent_usermessage(user_profile)
        return 'has_alert_word' in user_message.flags_list()

    def test_alert_flags(self) -> None:
        self.login('hamlet')
        user_profile_hamlet = self.example_user('hamlet')

        result = self.client_post('/json/users/me/alert_words',
                                  {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)
        self.assertEqual(set(result.json()['alert_words']), {'one', 'two', 'three'})

        # Alerts in the middle of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Normal alert one time"))
        # Alerts at the end of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Normal alert one"))
        # Alerts at the beginning of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "two normal alerts"))
        # Alerts with surrounding punctuation work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "This one? should alert"))
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Definitely time for three."))
        # Multiple alerts in a message work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "One two three o'clock"))
        # Alerts are case-insensitive.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "One o'clock"))
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Case of ONE, won't stop me"))

        # We don't cause alerts for matches in URLs.
        self.assertFalse(self.message_does_alert(user_profile_hamlet, "Don't alert on http://t.co/one/ urls"))
        self.assertFalse(self.message_does_alert(user_profile_hamlet, "Don't alert on http://t.co/one urls"))

    def test_update_alert_words(self) -> None:
        user_profile = self.example_user('hamlet')

        self.login_user(user_profile)
        result = self.client_post('/json/users/me/alert_words',
                                  {'alert_words': ujson.dumps(['ALERT'])})

        content = 'this is an ALERT for you'
        self.send_stream_message(user_profile, "Denmark", content)
        self.assert_json_success(result)

        original_message = most_recent_message(user_profile)

        user_message = most_recent_usermessage(user_profile)
        self.assertIn('has_alert_word', user_message.flags_list())

        result = self.client_patch("/json/messages/" + str(original_message.id), {
            'message_id': original_message.id,
            'content': 'new ALERT for you',
        })
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user_profile)
        self.assertEqual(user_message.message.content, 'new ALERT for you')
        self.assertIn('has_alert_word', user_message.flags_list())

        result = self.client_patch("/json/messages/" + str(original_message.id), {
            'message_id': original_message.id,
            'content': 'sorry false alarm',
        })
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user_profile)
        self.assertEqual(user_message.message.content, 'sorry false alarm')
        self.assertNotIn('has_alert_word', user_message.flags_list())
