from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

from django.conf import settings

from zerver.apps import flush_cache
from zerver.lib.cache import (
    MEMCACHED_MAX_KEY_LENGTH,
    InvalidCacheKeyException,
    NotFoundInCache,
    bulk_cached_fetch,
    cache_delete,
    cache_delete_many,
    cache_get,
    cache_get_many,
    cache_set,
    cache_set_many,
    cache_with_key,
    get_cache_with_key,
    safe_cache_get_many,
    safe_cache_set_many,
    user_profile_by_email_cache_key,
    validate_cache_key,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import queries_captured
from zerver.models import UserProfile, get_system_bot, get_user_profile_by_email


class AppsTest(ZulipTestCase):
    def test_cache_gets_flushed(self) -> None:
        with patch('zerver.apps.logging.info') as mock_logging:
            with patch('zerver.apps.cache.clear') as mock:
                # The argument to flush_cache doesn't matter
                flush_cache(Mock())
                mock.assert_called_once()
            mock_logging.assert_called_once()

class CacheKeyValidationTest(ZulipTestCase):
    def test_validate_cache_key(self) -> None:
        validate_cache_key('nice_Ascii:string!~')
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key('utf8_character:ą')
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key('new_line_character:\n')
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key('control_character:\r')
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key('whitespace_character: ')
        with self.assertRaises(InvalidCacheKeyException):
            validate_cache_key('too_long:' + 'X'*MEMCACHED_MAX_KEY_LENGTH)

        with self.assertRaises(InvalidCacheKeyException):
            # validate_cache_key does validation on a key with the
            # KEY_PREFIX appended to the start, so even though we're
            # passing something "short enough" here, it becomes too
            # long after appending KEY_PREFIX.
            validate_cache_key('X' * (MEMCACHED_MAX_KEY_LENGTH - 2))

    def test_cache_functions_raise_exception(self) -> None:
        invalid_key = 'invalid_character:\n'
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
            return f'CacheWithKeyDecoratorTest:invalid_character:ą:{user_id}'

        @cache_with_key(invalid_characters_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user('hamlet')
        with patch('zerver.lib.cache.cache_set') as mock_set, \
                patch('zerver.lib.cache.logger.warning') as mock_warn:
            with queries_captured() as queries:
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assertEqual(result, hamlet)
            self.assert_length(queries, 1)
            mock_set.assert_not_called()
            mock_warn.assert_called_once()

    def test_cache_with_key_key_too_long(self) -> None:
        def too_long_cache_key_function(user_id: int) -> str:
            return 'CacheWithKeyDecoratorTest:very_long_key:{}:{}'.format('a'*250, user_id)

        @cache_with_key(too_long_cache_key_function, timeout=1000)
        def get_user_function_with_bad_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user('hamlet')

        with patch('zerver.lib.cache.cache_set') as mock_set, \
                patch('zerver.lib.cache.logger.warning') as mock_warn:
            with queries_captured() as queries:
                result = get_user_function_with_bad_cache_keys(hamlet.id)

            self.assertEqual(result, hamlet)
            self.assert_length(queries, 1)
            mock_set.assert_not_called()
            mock_warn.assert_called_once()

    def test_cache_with_key_good_key(self) -> None:
        def good_cache_key_function(user_id: int) -> str:
            return f'CacheWithKeyDecoratorTest:good_cache_key:{user_id}'

        @cache_with_key(good_cache_key_function, timeout=1000)
        def get_user_function_with_good_cache_keys(user_id: int) -> UserProfile:
            return UserProfile.objects.get(id=user_id)

        hamlet = self.example_user('hamlet')

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
            return f'CacheWithKeyDecoratorTest:test_cache_with_key_none_values:{user_id}'

        @cache_with_key(cache_key_function, timeout=1000)
        def get_user_function_can_return_none(user_id: int) -> Optional[UserProfile]:
            try:
                return UserProfile.objects.get(id=user_id)
            except UserProfile.DoesNotExist:
                return None

        last_user_id = UserProfile.objects.last().id
        with queries_captured() as queries:
            result = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result, None)
        self.assert_length(queries, 1)

        with queries_captured(keep_cache_warm=True) as queries:
            result_two = get_user_function_can_return_none(last_user_id + 1)

        self.assertEqual(result_two, None)
        self.assert_length(queries, 0)

class GetCacheWithKeyDecoratorTest(ZulipTestCase):
    def test_get_cache_with_good_key(self) -> None:
        # Test with a good cache key function, but a get_user function
        # that always returns None just to make it convenient to tell
        # whether the cache was used (whatever we put in the cache) or
        # we got the result from calling the function (None)

        def good_cache_key_function(user_id: int) -> str:
            return f'CacheWithKeyDecoratorTest:good_cache_key:{user_id}'

        @get_cache_with_key(good_cache_key_function)
        def get_user_function_with_good_cache_keys(user_id: int) -> Any:  # nocoverage
            return

        hamlet = self.example_user('hamlet')
        with patch('zerver.lib.cache.logger.warning') as mock_warn:
            with self.assertRaises(NotFoundInCache):
                get_user_function_with_good_cache_keys(hamlet.id)
            mock_warn.assert_not_called()

        cache_set(good_cache_key_function(hamlet.id), hamlet)
        result = get_user_function_with_good_cache_keys(hamlet.id)
        self.assertEqual(result, hamlet)

    def test_get_cache_with_bad_key(self) -> None:
        def bad_cache_key_function(user_id: int) -> str:
            return f'CacheWithKeyDecoratorTest:invalid_character:ą:{user_id}'

        @get_cache_with_key(bad_cache_key_function)
        def get_user_function_with_bad_cache_keys(user_id: int) -> Any:  # nocoverage
            return

        hamlet = self.example_user('hamlet')
        with patch('zerver.lib.cache.logger.warning') as mock_warn:
            with self.assertRaises(NotFoundInCache):
                get_user_function_with_bad_cache_keys(hamlet.id)
            mock_warn.assert_called_once()

class SafeCacheFunctionsTest(ZulipTestCase):
    def test_safe_cache_functions_with_all_good_keys(self) -> None:
        items = {"SafeFunctionsTest:key1": 1, "SafeFunctionsTest:key2": 2, "SafeFunctionsTest:key3": 3}
        safe_cache_set_many(items)

        result = safe_cache_get_many(list(items.keys()))
        for key, value in result.items():
            self.assertEqual(value, items[key])

    def test_safe_cache_functions_with_all_bad_keys(self) -> None:
        items = {"SafeFunctionsTest:\nbadkey1": 1, "SafeFunctionsTest:\nbadkey2": 2}
        with patch('zerver.lib.cache.logger.warning') as mock_warn:
            safe_cache_set_many(items)
            mock_warn.assert_called_once()
            self.assertEqual(
                mock_warn.call_args[0][1],
                ['SafeFunctionsTest:\nbadkey1', 'SafeFunctionsTest:\nbadkey2'],
            )

        with patch('zerver.lib.cache.logger.warning') as mock_warn:
            result = safe_cache_get_many(list(items.keys()))
            mock_warn.assert_called_once()
            self.assertEqual(
                mock_warn.call_args[0][1],
                ['SafeFunctionsTest:\nbadkey1', 'SafeFunctionsTest:\nbadkey2'],
            )

            self.assertEqual(result, {})

    def test_safe_cache_functions_with_good_and_bad_keys(self) -> None:
        bad_items = {"SafeFunctionsTest:\nbadkey1": 1, "SafeFunctionsTest:\nbadkey2": 2}
        good_items = {"SafeFunctionsTest:goodkey1": 3, "SafeFunctionsTest:goodkey2": 4}
        items = {**good_items, **bad_items}

        with patch('zerver.lib.cache.logger.warning') as mock_warn:
            safe_cache_set_many(items)
            mock_warn.assert_called_once()
            self.assertEqual(
                mock_warn.call_args[0][1],
                ['SafeFunctionsTest:\nbadkey1', 'SafeFunctionsTest:\nbadkey2'],
            )

        with patch('zerver.lib.cache.logger.warning') as mock_warn:
            result = safe_cache_get_many(list(items.keys()))
            mock_warn.assert_called_once()
            self.assertEqual(
                mock_warn.call_args[0][1],
                ['SafeFunctionsTest:\nbadkey1', 'SafeFunctionsTest:\nbadkey2'],
            )

            self.assertEqual(result, good_items)

class BotCacheKeyTest(ZulipTestCase):
    def test_bot_profile_key_deleted_on_save(self) -> None:
        # Get the profile cached on both cache keys:
        user_profile = get_user_profile_by_email(settings.EMAIL_GATEWAY_BOT)
        bot_profile = get_system_bot(settings.EMAIL_GATEWAY_BOT)
        self.assertEqual(user_profile, bot_profile)

        # Flip the setting and save:
        flipped_setting = not bot_profile.is_api_super_user
        bot_profile.is_api_super_user = flipped_setting
        bot_profile.save()

        # The .save() should have deleted cache keys, so if we fetch again,
        # the returned objects should have is_api_super_user set correctly.
        bot_profile2 = get_system_bot(settings.EMAIL_GATEWAY_BOT)
        self.assertEqual(bot_profile2.is_api_super_user, flipped_setting)

        user_profile2 = get_user_profile_by_email(settings.EMAIL_GATEWAY_BOT)
        self.assertEqual(user_profile2.is_api_super_user, flipped_setting)

def get_user_email(user: UserProfile) -> str:
    return user.email  # nocoverage

class GenericBulkCachedFetchTest(ZulipTestCase):
    def test_query_function_called_only_if_needed(self) -> None:
        # Get the user cached:
        hamlet = get_user_profile_by_email(self.example_email("hamlet"))

        class CustomException(Exception):
            pass

        def query_function(emails: List[str]) -> List[UserProfile]:
            raise CustomException("The query function was called")

        # query_function shouldn't be called, because the only requested object
        # is already cached:
        result: Dict[str, UserProfile] = bulk_cached_fetch(
            cache_key_function=user_profile_by_email_cache_key,
            query_function=query_function,
            object_ids=[self.example_email("hamlet")],
            id_fetcher=get_user_email,
        )
        self.assertEqual(result, {hamlet.delivery_email: hamlet})
        with self.assertLogs(level='INFO') as info_log:
            flush_cache(Mock())
        self.assertEqual(info_log.output, [
            'INFO:root:Clearing memcached cache after migrations'
        ])

        # With the cache flushed, the query_function should get called:
        with self.assertRaises(CustomException):
            result = bulk_cached_fetch(
                cache_key_function=user_profile_by_email_cache_key,
                query_function=query_function,
                object_ids=[self.example_email("hamlet")],
                id_fetcher=get_user_email,
            )

    def test_empty_object_ids_list(self) -> None:
        class CustomException(Exception):
            pass

        def cache_key_function(email: str) -> str:  # nocoverage -- this is just here to make sure it's not called
            raise CustomException("The cache key function was called")

        def query_function(emails: List[str]) -> List[UserProfile]:  # nocoverage -- this is just here to make sure it's not called
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
