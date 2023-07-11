from typing import Dict, List, Optional
from unittest.mock import Mock, patch

from django.conf import settings

from zerver.apps import flush_cache
from zerver.lib.cache import (
    MAX_NUM_ROWS_FOR_CACHE_LOOKUP,
    MEMCACHED_MAX_KEY_LENGTH,
    InvalidCacheKeyError,
    bulk_cached_fetch,
    cache_delete,
    cache_delete_many,
    cache_get,
    cache_get_many,
    cache_set,
    cache_set_many,
    cache_with_key,
    generic_bulk_cached_fetch,
    safe_cache_get_many,
    safe_cache_set_many,
    user_profile_by_id_cache_key,
    validate_cache_key,
)
from zerver.lib.create_user import create_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile, get_realm, get_system_bot, get_user, get_user_profile_by_id


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
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("utf8_character:ą")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("new_line_character:\n")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("control_character:\r")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("whitespace_character: ")
        with self.assertRaises(InvalidCacheKeyError):
            validate_cache_key("too_long:" + "X" * MEMCACHED_MAX_KEY_LENGTH)

        with self.assertRaises(InvalidCacheKeyError):
            # validate_cache_key does validation on a key with the
            # KEY_PREFIX appended to the start, so even though we're
            # passing something "short enough" here, it becomes too
            # long after appending KEY_PREFIX.
            validate_cache_key("X" * (MEMCACHED_MAX_KEY_LENGTH - 2))

    def test_cache_functions_raise_exception(self) -> None:
        invalid_key = "invalid_character:\n"
        good_key = "good_key"
        with self.assertRaises(InvalidCacheKeyError):
            cache_get(invalid_key)
        with self.assertRaises(InvalidCacheKeyError):
            cache_set(invalid_key, 0)
        with self.assertRaises(InvalidCacheKeyError):
            cache_delete(invalid_key)

        with self.assertRaises(InvalidCacheKeyError):
            cache_get_many([good_key, invalid_key])
        with self.assertRaises(InvalidCacheKeyError):
            cache_set_many({good_key: 0, invalid_key: 1})
        with self.assertRaises(InvalidCacheKeyError):
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
            with self.assert_database_query_count(1):
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assert_length(m.output, 1)
            self.assertEqual(result, hamlet)
            mock_set.assert_not_called()

    def test_cache_with_key_key_too_long(self) -> None:
        def too_long_cache_key_function(user_id: int) -> str:
            return "CacheWithKeyDecoratorTest:very_long_key:{}:{}".format("a" * 250, user_id)

        @cache_with_key(too_long_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")

        with patch("zerver.lib.cache.cache_set") as mock_set, self.assertLogs(level="WARNING") as m:
            with self.assert_database_query_count(1):
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assert_length(m.output, 1)
            self.assertEqual(result, hamlet)
            mock_set.assert_not_called()

    def test_cache_with_key_good_key(self) -> None:
        def good_cache_key_function(user_id: int) -> str:
            return f"CacheWithKeyDecoratorTest:good_cache_key:{user_id}"

        @cache_with_key(good_cache_key_function, timeout=1000)
        def get_user_function_with_good_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user("hamlet")

        with self.assert_database_query_count(1):
            result = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result, hamlet)

        # The previous function call should have cached the result correctly, so now
        # no database queries should happen:
        with self.assert_database_query_count(0, keep_cache_warm=True):
            result_two = get_user_function_with_good_cache_keys(hamlet.id)

        self.assertEqual(result_two, hamlet)

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
        with self.assert_database_query_count(1):
            result = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result, None)

        with self.assert_database_query_count(0, keep_cache_warm=True):
            result_two = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result_two, None)


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
    def test_max_num_rows_to_database(self) -> None:
        realm = get_realm("zulip")

        def cache_key_function(user_id: int) -> str:
            return f"test_user_key{user_id}"

        def id_fetcher(user: UserProfile) -> int:
            return user.id

        def cache_transformer(user: UserProfile) -> str:
            return user.email

        extractor = lambda obj: obj
        setter = lambda obj: obj

        def get_user_dict(object_ids: List[int]) -> Dict[int, str]:
            def query_function(user_ids: List[int]) -> List[UserProfile]:
                # If we get called, we are assuming in this test that
                # we either skipped the cache entirely or the cache
                # was cold.
                self.assertEqual(user_ids, object_ids)
                return list(UserProfile.objects.filter(id__in=user_ids).only("id", "email"))

            return generic_bulk_cached_fetch(
                cache_key_function=cache_key_function,
                query_function=query_function,
                object_ids=object_ids,
                extractor=extractor,
                setter=setter,
                cache_transformer=cache_transformer,
                id_fetcher=id_fetcher,
            )

        new_users = [
            create_user(
                email=f"user{i}@zulip.com",
                password=None,
                realm=realm,
                full_name="full_name",
            )
            for i in range(MAX_NUM_ROWS_FOR_CACHE_LOOKUP + 1)
        ]

        new_user_emails = {user.id: user.email for user in new_users}

        big_user_id_list = [user.id for user in new_users]
        small_user_id_list = big_user_id_list[: MAX_NUM_ROWS_FOR_CACHE_LOOKUP - 1]

        expected_big_result = new_user_emails
        expected_small_result = {
            user_id: new_user_emails[user_id] for user_id in small_user_id_list
        }

        # Test small queries first
        with self.assert_database_query_count(1):
            result = get_user_dict(small_user_id_list)
        self.assertEqual(result, expected_small_result)

        with self.assert_database_query_count(0, keep_cache_warm=True):
            result = get_user_dict(small_user_id_list)
        self.assertEqual(result, expected_small_result)

        # Now test big queries
        with self.assert_database_query_count(1):
            result = get_user_dict(big_user_id_list)
        self.assertEqual(result, expected_big_result)

        # We still hit the database even though the cache is warm.
        with self.assert_database_query_count(1, keep_cache_warm=True):
            result = get_user_dict(big_user_id_list)
        self.assertEqual(result, expected_big_result)

    def test_query_function_called_only_if_needed(self) -> None:
        hamlet = self.example_user("hamlet")
        # Get the user cached:
        get_user_profile_by_id(hamlet.id)

        class CustomError(Exception):
            pass

        def query_function(ids: List[int]) -> List[UserProfile]:
            raise CustomError("The query function was called")

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

        # With the cache flushed, the query_function should get called:
        with self.assertRaises(CustomError):
            result = bulk_cached_fetch(
                cache_key_function=user_profile_by_id_cache_key,
                query_function=query_function,
                object_ids=[hamlet.id],
                id_fetcher=get_user_id,
            )

    def test_empty_object_ids_list(self) -> None:
        class CustomError(Exception):
            pass

        def cache_key_function(
            email: str,
        ) -> str:  # nocoverage -- this is just here to make sure it's not called
            raise CustomError("The cache key function was called")

        def query_function(
            emails: List[str],
        ) -> List[UserProfile]:  # nocoverage -- this is just here to make sure it's not called
            raise CustomError("The query function was called")

        # query_function and cache_key_function shouldn't be called, because
        # objects_ids is empty, so there's nothing to do.
        result: Dict[str, UserProfile] = bulk_cached_fetch(
            cache_key_function=cache_key_function,
            query_function=query_function,
            object_ids=[],
            id_fetcher=get_user_email,
        )
        self.assertEqual(result, {})
