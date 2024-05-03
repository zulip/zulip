import orjson

from zerver.actions.alert_words import do_add_watched_phrases, do_remove_watched_phrases
from zerver.lib.alert_words import (
    WatchedPhraseData,
    user_alert_words,
    user_watched_phrases,
    watched_phrases_in_realm,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message, most_recent_usermessage
from zerver.models import AlertWord, UserProfile


class AlertWordTests(ZulipTestCase):
    interesting_alert_word_list = ["alert", "multi-word word", "☃"]
    interesting_watched_phrases_list = [
        WatchedPhraseData(watched_phrase="alert"),
        WatchedPhraseData(watched_phrase="multi-word word"),
        WatchedPhraseData(watched_phrase="☃"),
    ]

    interesting_watched_phrases_list_response = [
        {"watched_phrase": "alert"},
        {"watched_phrase": "multi-word word"},
        {"watched_phrase": "☃"},
    ]

    def get_user(self) -> UserProfile:
        # One nice thing about Hamlet is that he is
        # already subscribed to Denmark.
        user = self.example_user("hamlet")

        # delete words from populate_db to simplify tests
        AlertWord.objects.filter(user_profile=user).delete()
        return user

    def test_internal_endpoint(self) -> None:
        user = self.get_user()
        self.login_user(user)

        params = {
            "alert_words": orjson.dumps(["milk", "cookies"]).decode(),
        }
        result = self.client_post("/json/users/me/alert_words", params)
        self.assert_json_success(result)

        words = user_alert_words(user)
        self.assertEqual(set(words), {"milk", "cookies"})

    def test_watched_phrases_internal_endpoint(self) -> None:
        user = self.get_user()
        self.login_user(user)

        params = {
            "watched_phrases": orjson.dumps(
                [{"watched_phrase": "milk"}, {"watched_phrase": "cookies"}]
            ).decode(),
        }
        result = self.client_post("/json/users/me/watched_phrases", params)
        self.assert_json_success(result)

        phrases = [w.dict() for w in user_watched_phrases(user)]
        self.assertEqual(phrases, [{"watched_phrase": "milk"}, {"watched_phrase": "cookies"}])

    def test_default_no_words(self) -> None:
        """
        Users start out with no alert words.
        """
        user = self.get_user()
        words = user_alert_words(user)
        self.assertEqual(words, [])

    def test_default_no_phrases(self) -> None:
        """
        Users start out with no watched phrases.
        """
        user = self.get_user()
        phrases = [w.dict() for w in user_watched_phrases(user)]
        self.assertEqual(phrases, [])

    def test_basics(self) -> None:
        """
        Verifies the basic behavior of modifying watched phrases.

        Also verifies the cache-flushing behavior.
        """
        user = self.get_user()
        realm_watched_phrases = watched_phrases_in_realm(user.realm)
        self.assert_length(realm_watched_phrases.get(user.id, []), 0)

        # Add several phrases, including multi-word and non-ascii words.
        do_add_watched_phrases(user, self.interesting_watched_phrases_list)

        phrases = [w.dict() for w in user_watched_phrases(user)]
        self.assertEqual(phrases, self.interesting_watched_phrases_list_response)
        realm_watched_phrases = watched_phrases_in_realm(user.realm)
        self.assert_length(realm_watched_phrases[user.id], 3)

        # Test the case-insensitivity of adding phrases
        do_add_watched_phrases(
            user,
            {WatchedPhraseData(watched_phrase="ALert"), WatchedPhraseData(watched_phrase="ALERT")},
        )
        phrases = [w.dict() for w in user_watched_phrases(user)]
        self.assertEqual(phrases, self.interesting_watched_phrases_list_response)
        realm_watched_phrases = watched_phrases_in_realm(user.realm)
        self.assert_length(realm_watched_phrases[user.id], 3)

        # Test the case-insensitivity of removing phrases
        do_remove_watched_phrases(user, {"ALert"})
        phrases = [w.dict() for w in user_watched_phrases(user)]
        self.assertEqual(phrases, [{"watched_phrase": "multi-word word"}, {"watched_phrase": "☃"}])
        realm_watched_phrases = watched_phrases_in_realm(user.realm)
        self.assert_length(realm_watched_phrases[user.id], 2)

    def test_remove_watched_phrases(self) -> None:
        """
        Removing watched phrases works via do_remove_watched_phrases, even
        for multi-word and non-ascii words.
        """
        user = self.get_user()

        expected_remaining_watched_phrases = set(self.interesting_watched_phrases_list)
        do_add_watched_phrases(user, self.interesting_watched_phrases_list)

        for phrase in self.interesting_watched_phrases_list:
            do_remove_watched_phrases(user, [phrase.watched_phrase])
            expected_remaining_watched_phrases.remove(phrase)
            actual_remaining_watched_phrases = user_watched_phrases(user)
            self.assertEqual(
                set(actual_remaining_watched_phrases), set(expected_remaining_watched_phrases)
            )

    def test_realm_watched_phrases(self) -> None:
        """
        We can gather watched phrases for an entire realm via
        watched_phrases_in_realm. Alerts added for one user do not impact other
        users.
        """

        # Clear all the words that we got from populate_db.
        AlertWord.objects.all().delete()

        user1 = self.get_user()

        do_add_watched_phrases(user1, self.interesting_watched_phrases_list)

        user2 = self.example_user("othello")
        do_add_watched_phrases(user2, [WatchedPhraseData(watched_phrase="another")])

        realm_phrases = watched_phrases_in_realm(user2.realm)
        self.assert_length(realm_phrases, 2)
        self.assertEqual(set(realm_phrases.keys()), {user1.id, user2.id})
        self.assertEqual(set(realm_phrases[user1.id]), {"alert", "multi-word word", "☃"})
        self.assertEqual(set(realm_phrases[user2.id]), {"another"})

    def test_json_list_default(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_get("/json/users/me/alert_words")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["alert_words"], [])

    def test_json_list_default_watched_phrases(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_get("/json/users/me/watched_phrases")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["watched_phrases"], [])

    def test_json_list_nonempty(self) -> None:
        user = self.get_user()
        do_add_watched_phrases(
            user,
            [
                WatchedPhraseData(watched_phrase="one"),
                WatchedPhraseData(watched_phrase="two"),
                WatchedPhraseData(watched_phrase="three"),
            ],
        )

        self.login_user(user)
        result = self.client_get("/json/users/me/alert_words")
        response_dict = self.assert_json_success(result)
        self.assertEqual(set(response_dict["alert_words"]), {"one", "two", "three"})

    def test_json_list_nonempty_watched_phrases(self) -> None:
        user = self.get_user()
        do_add_watched_phrases(
            user,
            [
                WatchedPhraseData(watched_phrase="one"),
                WatchedPhraseData(watched_phrase="two"),
                WatchedPhraseData(watched_phrase="three"),
            ],
        )

        self.login_user(user)
        result = self.client_get("/json/users/me/watched_phrases")
        response_dict = self.assert_json_success(result)
        self.assertEqual(
            (response_dict["watched_phrases"]),
            [{"watched_phrase": "one"}, {"watched_phrase": "two"}, {"watched_phrase": "three"}],
        )

    def test_json_list_add(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/alert_words",
            {"alert_words": orjson.dumps(["one ", "\n two", "three"]).decode()},
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(set(response_dict["alert_words"]), {"one", "two", "three"})

        result = self.client_post(
            "/json/users/me/alert_words",
            {"alert_words": orjson.dumps(["long" * 26]).decode()},
        )
        self.assert_json_error(result, "alert_words[0] is too long (limit: 100 characters)")

    def test_json_list_add_watched_phrases(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/watched_phrases",
            {
                "watched_phrases": orjson.dumps(
                    [
                        {"watched_phrase": "one "},
                        {"watched_phrase": "\n two"},
                        {"watched_phrase": "three"},
                    ]
                ).decode()
            },
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(
            response_dict["watched_phrases"],
            [{"watched_phrase": "one"}, {"watched_phrase": "two"}, {"watched_phrase": "three"}],
        )

        result = self.client_post(
            "/json/users/me/watched_phrases",
            {"watched_phrases": orjson.dumps([{"watched_phrase": ("long" * 26)}]).decode()},
        )
        self.assert_json_error(
            result, """watched_phrases[0]["watched_phrase"] is too long (limit: 100 characters)"""
        )

    def test_json_list_remove(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/alert_words",
            {"alert_words": orjson.dumps(["one", "two", "three"]).decode()},
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(set(response_dict["alert_words"]), {"one", "two", "three"})

        result = self.client_delete(
            "/json/users/me/alert_words", {"alert_words": orjson.dumps(["one"]).decode()}
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(set(response_dict["alert_words"]), {"two", "three"})

    def test_json_list_remove_watched_phrases(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/watched_phrases",
            {
                "watched_phrases": orjson.dumps(
                    [
                        {"watched_phrase": "one"},
                        {"watched_phrase": "two"},
                        {"watched_phrase": "three"},
                    ]
                ).decode()
            },
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(
            response_dict["watched_phrases"],
            [{"watched_phrase": "one"}, {"watched_phrase": "two"}, {"watched_phrase": "three"}],
        )

        result = self.client_delete(
            "/json/users/me/watched_phrases", {"watched_phrases": orjson.dumps(["one"]).decode()}
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(
            response_dict["watched_phrases"],
            [{"watched_phrase": "two"}, {"watched_phrase": "three"}],
        )

    def message_does_alert(self, user: UserProfile, message: str) -> bool:
        """Send a bunch of messages as othello, so our user is notified"""
        self.send_stream_message(self.example_user("othello"), "Denmark", message)
        user_message = most_recent_usermessage(user)
        return "has_alert_word" in user_message.flags_list()

    def test_alert_flags(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/alert_words",
            {"alert_words": orjson.dumps(["one", "two", "three"]).decode()},
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(set(response_dict["alert_words"]), {"one", "two", "three"})

        # Alerts in the middle of messages work.
        self.assertTrue(self.message_does_alert(user, "Normal alert one time"))
        # Alerts at the end of messages work.
        self.assertTrue(self.message_does_alert(user, "Normal alert one"))
        # Alerts at the beginning of messages work.
        self.assertTrue(self.message_does_alert(user, "two normal alerts"))
        # Alerts with surrounding punctuation work.
        self.assertTrue(self.message_does_alert(user, "This one? should alert"))
        self.assertTrue(self.message_does_alert(user, "Definitely time for three."))
        # Multiple alerts in a message work.
        self.assertTrue(self.message_does_alert(user, "One two three o'clock"))
        # Alerts are case-insensitive.
        self.assertTrue(self.message_does_alert(user, "One o'clock"))
        self.assertTrue(self.message_does_alert(user, "Case of ONE, won't stop me"))

        # We don't cause alerts for matches in URLs.
        self.assertFalse(self.message_does_alert(user, "Don't alert on http://t.co/one/ URLs"))
        self.assertFalse(self.message_does_alert(user, "Don't alert on http://t.co/one URLs"))

        # We don't cause alerts for matches within a word.
        self.assertFalse(
            self.message_does_alert(user, "Don't alert on clone, twofold or seventytwofold")
        )

    def test_watched_phrases_flags(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/watched_phrases",
            {
                "watched_phrases": orjson.dumps(
                    [
                        {"watched_phrase": "one"},
                        {"watched_phrase": "two"},
                        {"watched_phrase": "three"},
                    ]
                ).decode()
            },
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(
            response_dict["watched_phrases"],
            [{"watched_phrase": "one"}, {"watched_phrase": "two"}, {"watched_phrase": "three"}],
        )

        # Alerts in the middle of messages work.
        self.assertTrue(self.message_does_alert(user, "Normal alert one time"))
        # Alerts at the end of messages work.
        self.assertTrue(self.message_does_alert(user, "Normal alert one"))
        # Alerts at the beginning of messages work.
        self.assertTrue(self.message_does_alert(user, "two normal alerts"))
        # Alerts with surrounding punctuation work.
        self.assertTrue(self.message_does_alert(user, "This one? should alert"))
        self.assertTrue(self.message_does_alert(user, "Definitely time for three."))
        # Multiple alerts in a message work.
        self.assertTrue(self.message_does_alert(user, "One two three o'clock"))
        # Alerts are case-insensitive.
        self.assertTrue(self.message_does_alert(user, "One o'clock"))
        self.assertTrue(self.message_does_alert(user, "Case of ONE, won't stop me"))

        # We don't cause alerts for matches in URLs.
        self.assertFalse(self.message_does_alert(user, "Don't alert on http://t.co/one/ URLs"))
        self.assertFalse(self.message_does_alert(user, "Don't alert on http://t.co/one URLs"))

        # We don't cause alerts for matches within a word.
        self.assertFalse(
            self.message_does_alert(user, "Don't alert on clone, twofold or seventytwofold")
        )

    def test_update_alert_words(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/alert_words", {"alert_words": orjson.dumps(["ALERT"]).decode()}
        )

        content = "this is an ALERT for you"
        self.send_stream_message(user, "Denmark", content)
        self.assert_json_success(result)

        original_message = most_recent_message(user)

        user_message = most_recent_usermessage(user)
        self.assertIn("has_alert_word", user_message.flags_list())

        result = self.client_patch(
            "/json/messages/" + str(original_message.id),
            {
                "content": "new ALERT for you",
            },
        )
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user)
        self.assertEqual(user_message.message.content, "new ALERT for you")
        self.assertIn("has_alert_word", user_message.flags_list())

        result = self.client_patch(
            "/json/messages/" + str(original_message.id),
            {
                "content": "sorry false alarm",
            },
        )
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user)
        self.assertEqual(user_message.message.content, "sorry false alarm")
        self.assertNotIn("has_alert_word", user_message.flags_list())

    def test_update_watched_phrases(self) -> None:
        user = self.get_user()
        self.login_user(user)

        result = self.client_post(
            "/json/users/me/watched_phrases",
            {"watched_phrases": orjson.dumps([{"watched_phrase": "ALERT"}]).decode()},
        )

        content = "this is an ALERT for you"
        self.send_stream_message(user, "Denmark", content)
        self.assert_json_success(result)

        original_message = most_recent_message(user)

        user_message = most_recent_usermessage(user)
        self.assertIn("has_alert_word", user_message.flags_list())

        result = self.client_patch(
            "/json/messages/" + str(original_message.id),
            {
                "content": "new ALERT for you",
            },
        )
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user)
        self.assertEqual(user_message.message.content, "new ALERT for you")
        self.assertIn("has_alert_word", user_message.flags_list())

        result = self.client_patch(
            "/json/messages/" + str(original_message.id),
            {
                "content": "sorry false alarm",
            },
        )
        self.assert_json_success(result)

        user_message = most_recent_usermessage(user)
        self.assertEqual(user_message.message.content, "sorry false alarm")
        self.assertNotIn("has_alert_word", user_message.flags_list())
