from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.sessions.models import Session

from zerver.apps import flush_cache
from zerver.lib.cache import (
    MEMCACHED_MAX_KEY_LENGTH,
    InvalidCacheKeyException,
    bulk_cached_fetch,
    cache_delete,
    cache_delete_many,
    cache_get,
    cache_get_many,
    cache_set,
    cache_set_many,
    cache_with_key,
    get_cache_backend,
    safe_cache_get_many,
    safe_cache_set_many,
    user_profile_by_id_cache_key,
    validate_cache_key,
)
from zerver.lib.cache_helpers import (
    client_cache_items,
    fill_remote_cache,
    huddle_cache_items,
    session_cache_items,
    stream_cache_items,
    user_cache_items,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import queries_captured
from zerver.models import (
    UserProfile,
    get_client,
    get_huddle,
    get_realm,
    get_stream,
    get_system_bot,
    get_user,
    get_user_profile_by_id,
)


class AppsTest(ZulipTestCase):
    def test_cache_gets_flushed(self) -> None:
        with self.assertLogs(level="INFO") as m:
            with patch("zerver.apps.cache.clear") as mock:
                # The argument to flush_cache doesn't matter
                flush_cache(Mock())
                mock.assert_called_once()
            self.assertEqual(m.output, ["INFO:root:Clearing memcached cache after migrations"])
            self.assert_length(m.output, 1)


class CacheKeyValidationTest(ZulipTestCase):
    def test_validate_cache_key(self) -> None:
        validate_cache_key("nice_Ascii:string!~")
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key("utf8_character:ą")
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key("new_line_character:\n")
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key("control_character:\r")
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key("whitespace_character: ")
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key("too_long:" + "X" * MEMCACHED_MAX_KEY_LENGTH)

        with self.assertRaises(InvalidCacheKeyException):
            # validate_cache_key does validation on a key with the
            # KEY_PREFIX appended to the start, so even though we're
            # passing something "short enough" here, it becomes too
            # long after appending KEY_PREFIX.
            validate_cache_key("X" * (MEMCACHED_MAX_KEY_LENGTH - 2))

    def test_cache_functions_raise_exception(self) -> None:
        invalid_key = "invalid_character:\n"
        good_key = "good_key"
        with self.assertRaises(InvalidCacheKeyException):
            cache_get(invalid_key)
        with self.assertRaises(InvalidCacheKeyException):
            cache_set(invalid_key, 0)
        with self.assertRaises(InvalidCacheKeyException):
            cache_delete(invalid_key)

        with self.assertRaises(InvalidCacheKeyException):
            cache_get_many([good_key, invalid_key])
        with self.assertRaises(InvalidCacheKeyException):
            cache_set_many({good_key: 0, invalid_key: 1})
        with self.assertRaises(InvalidCacheKeyException):
            cache_delete_many([good_key, invalid_key])


class CacheWithKeyDecoratorTest(ZulipTestCase):
    def test_cache_with_key_invalid_character(self) -> None:
        def invalid_characters_cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:invalid_character:ą:{user_id}"

        @cache_with_key(invalid_characters_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")
        with patch("zerver.lib.cache.cache_set") as mock_set, self.assertLogs(level="WARNING") as m:
            with queries_captured() as queries:
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assert_length(m.output, 1)
            self.assertEqual(result, hamlet)
            self.assert_length(queries, 1)
            mock_set.assert_not_called()

    def test_cache_with_key_key_too_long(self) -> None:
        def too_long_cache_key_function(user_id: int) -> str:
            return "CacheWithKeyDecoratorTest:very_long_key:{}:{}".format("a" * 250, user_id)

        @cache_with_key(too_long_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")

        with patch("zerver.lib.cache.cache_set") as mock_set, self.assertLogs(level="WARNING") as m:
            with queries_captured() as queries:
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assert_length(m.output, 1)
            self.assertEqual(result, hamlet)
            self.assert_length(queries, 1)
            mock_set.assert_not_called()

    def test_cache_with_key_good_key(self) -> None:
        def good_cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:good_cache_key:{user_id}"

        @cache_with_key(good_cache_key_function, timeout=1000)
        def get_user_function_with_good_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")

        with queries_captured() as queries:
            result = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result, hamlet)
        self.assert_length(queries, 1)

        # The previous function call should have cached the result correctly, so now
        # no database queries should happen:
        with queries_captured(keep_cache_warm=True) as queries_two:
            result_two = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result_two, hamlet)
        self.assert_length(queries_two, 0)

    def test_cache_with_key_none_values(self) -> None:
        def cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:test_cache_with_key_none_values:{user_id}"

        @cache_with_key(cache_key_function, timeout=1000)
        def get_user_function_can_return_none(user_id: int) -> Optional[UserProfile]:
            try:
                return UserProfile.objects.get(id=user_id)
            except UserProfile.DoesNotExist:
                return None

        last_user = UserProfile.objects.last()
        assert last_user is not None
        last_user_id = last_user.id
        with queries_captured() as queries:
            result = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result, None)
        self.assert_length(queries, 1)

        with queries_captured(keep_cache_warm=True) as queries:
            result_two = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result_two, None)
        self.assert_length(queries, 0)

    def test_cache_with_key_database(self) -> None:
        def good_cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:good_cache_key:{user_id}"

        @cache_with_key(good_cache_key_function, cache_name="database", with_statsd_key="stk")
        def get_user_function_with_good_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")
        mock_backend = get_cache_backend(None)

        with queries_captured() as queries:
            with patch("zerver.lib.cache.get_cache_backend", return_value=mock_backend):
                result = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result, hamlet)
        self.assert_length(queries, 1)

        # The previous function call should have cached the result correctly, so now
        # no database queries should happen:
        with queries_captured(keep_cache_warm=True) as queries_two:
            with patch("zerver.lib.cache.get_cache_backend", return_value=mock_backend):
                result_two = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result_two, hamlet)
        self.assert_length(queries_two, 0)


class SafeCacheFunctionsTest(ZulipTestCase):
    def test_safe_cache_functions_with_all_good_keys(self) -> None:
        items = {
            "SafeFunctionsTest:key1": 1,
            "SafeFunctionsTest:key2": 2,
            "SafeFunctionsTest:key3": 3,
        }
        safe_cache_set_many(items)

        result = safe_cache_get_many(list(items.keys()))
        for key, value in result.items():
            self.assertEqual(value, items[key])

    def test_safe_cache_functions_with_all_bad_keys(self) -> None:
        items = {"SafeFunctionsTest:\nbadkey1": 1, "SafeFunctionsTest:\nbadkey2": 2}
        with self.assertLogs(level="WARNING") as m:
            safe_cache_set_many(items)
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)

        with self.assertLogs(level="WARNING") as m:
            result = safe_cache_get_many(list(items.keys()))
            self.assertEqual(result, {})
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)

    def test_safe_cache_functions_with_good_and_bad_keys(self) -> None:
        bad_items = {"SafeFunctionsTest:\nbadkey1": 1, "SafeFunctionsTest:\nbadkey2": 2}
        good_items = {"SafeFunctionsTest:goodkey1": 3, "SafeFunctionsTest:goodkey2": 4}
        items = {**good_items, **bad_items}

        with self.assertLogs(level="WARNING") as m:
            safe_cache_set_many(items)
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)

        with self.assertLogs(level="WARNING") as m:
            result = safe_cache_get_many(list(items.keys()))
            self.assertEqual(result, good_items)
            self.assertIn(
                "WARNING:root:Invalid cache key used: ['SafeFunctionsTest:\\nbadkey1', 'SafeFunctionsTest:\\nbadkey2']",
                m.output[0],
            )
            self.assert_length(m.output, 1)


class BotCacheKeyTest(ZulipTestCase):
    def test_bot_profile_key_deleted_on_save(self) -> None:
        realm = get_realm(settings.SYSTEM_BOT_REALM)
        # Get the profile cached on both cache keys:
        user_profile = get_user(settings.EMAIL_GATEWAY_BOT, realm)
        bot_profile = get_system_bot(settings.EMAIL_GATEWAY_BOT, realm.id)
        self.assertEqual(user_profile, bot_profile)

        # Flip the setting and save:
        flipped_setting = not bot_profile.can_forge_sender
        bot_profile.can_forge_sender = flipped_setting
        bot_profile.save()

        # The .save() should have deleted cache keys, so if we fetch again,
        # the returned objects should have can_forge_sender set correctly.
        bot_profile2 = get_system_bot(settings.EMAIL_GATEWAY_BOT, realm.id)
        self.assertEqual(bot_profile2.can_forge_sender, flipped_setting)

        user_profile2 = get_user(settings.EMAIL_GATEWAY_BOT, realm)
        self.assertEqual(user_profile2.can_forge_sender, flipped_setting)


def get_user_id(user: UserProfile) -> int:
    return user.id  # nocoverage


def get_user_email(user: UserProfile) -> str:
    return user.email  # nocoverage


class GenericBulkCachedFetchTest(ZulipTestCase):
    def test_query_function_called_only_if_needed(self) -> None:
        hamlet = self.example_user("hamlet")
        # Get the user cached:
        get_user_profile_by_id(hamlet.id)

        class CustomException(Exception):
            pass

        def query_function(ids: List[int]) -> List[UserProfile]:
            raise AssertionError("query_function shouldn't be called.")

        # query_function shouldn't be called, because the only requested object
        # is already cached:
        result: Dict[int, UserProfile] = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=query_function,
            object_ids=[hamlet.id],
            id_fetcher=get_user_id,
        )
        self.assertEqual(result, {hamlet.id: hamlet})
        with self.assertLogs(level="INFO") as info_log:
            flush_cache(Mock())
        self.assertEqual(info_log.output, ["INFO:root:Clearing memcached cache after migrations"])

        new_query_function_called = False

        def new_query_function(ids: List[int]) -> List[UserProfile]:
            nonlocal new_query_function_called
            new_query_function_called = True
            return [hamlet]

        # With the cache flushed, the query_function should get called:
        result = bulk_cached_fetch(
            cache_key_function=user_profile_by_id_cache_key,
            query_function=new_query_function,
            object_ids=[hamlet.id],
            id_fetcher=get_user_id,
        )
        self.assertTrue(new_query_function_called)

    def test_empty_object_ids_list(self) -> None:
        class CustomException(Exception):
            pass

        def cache_key_function(
            email: str,
        ) -> str:  # nocoverage -- this is just here to make sure it's not called
            raise CustomException("The cache key function was called")

        def query_function(
            emails: List[str],
        ) -> List[UserProfile]:  # nocoverage -- this is just here to make sure it's not called
            raise CustomException("The query function was called")

        # query_function and cache_key_function shouldn't be called, because
        # objects_ids is empty, so there's nothing to do.
        result: Dict[str, UserProfile] = bulk_cached_fetch(
            cache_key_function=cache_key_function,
            query_function=query_function,
            object_ids=[],
            id_fetcher=get_user_email,
        )
        self.assertEqual(result, {})


class CacheHelpers(ZulipTestCase):
    def test_fill_remote_cache(self) -> None:
        for ctype in ["user", "client", "stream", "huddle", "session"]:
            with patch("zerver.lib.cache.get_remote_cache_time", return_value=0):
                with self.assertLogs(level="INFO") as m:
                    fill_remote_cache(ctype)
                self.assertEqual(
                    m.output,
                    [
                        f"INFO:root:Successfully populated {ctype} cache!  "
                        "Consumed 1 remote cache queries (0.0 time)"
                    ],
                )

        with self.assertRaises(KeyError):
            fill_remote_cache("unknown")

    def test_batch_fill_remote_cache(self) -> None:
        with patch(
            "zerver.lib.cache_helpers.cache_fillers",
            {"user": (lambda: [i for i in range(100)], lambda a, b: None, 1000, 4)},
        ):
            with patch("zerver.lib.cache.get_remote_cache_time", return_value=0):
                with self.assertLogs(level="INFO"):
                    fill_remote_cache("user")

    def test_getitems(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        items_for_remote_cache: Dict[str, Any] = {}
        user_cache_items(items_for_remote_cache, hamlet)
        stream_cache_items(items_for_remote_cache, get_stream("Denmark", hamlet.realm))
        client_cache_items(items_for_remote_cache, get_client("test"))
        huddle_cache_items(items_for_remote_cache, get_huddle([hamlet.id, cordelia.id]))
        session_cache_items(items_for_remote_cache, Session(session_key="foo"))

        class MockSessionStore(object):
            cache_key: str = "42"

            def decode(*args) -> str:
                return "meaning of the universe"

        with self.settings(SESSION_ENGINE="zerver.lib.safe_session_cached_db"):
            with patch(
                "zerver.lib.sessions.session_engine.SessionStore", return_value=MockSessionStore()
            ):
                session_cache_items(items_for_remote_cache, Session(session_key="bar"))
                self.assertEqual(items_for_remote_cache["42"], "meaning of the universe")
