from django.conf import settings

from mock import Mock, patch
from typing import List, Dict

from zerver.apps import flush_cache
from zerver.lib.cache import generic_bulk_cached_fetch, user_profile_by_email_cache_key
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_system_bot, get_user_profile_by_email, UserProfile

class AppsTest(ZulipTestCase):
    def test_cache_gets_flushed(self) -> None:
        with patch('zerver.apps.logging.info') as mock_logging:
            with patch('zerver.apps.cache.clear') as mock:
                # The argument to flush_cache doesn't matter
                flush_cache(Mock())
                mock.assert_called_once()
            mock_logging.assert_called_once()

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
        result = generic_bulk_cached_fetch(
            cache_key_function=user_profile_by_email_cache_key,
            query_function=query_function,
            object_ids=[self.example_email("hamlet")]
        )  # type: Dict[str, UserProfile]
        self.assertEqual(result, {hamlet.email: hamlet})

        flush_cache(Mock())
        # With the cache flushed, the query_function should get called:
        with self.assertRaises(CustomException):
            generic_bulk_cached_fetch(
                cache_key_function=user_profile_by_email_cache_key,
                query_function=query_function,
                object_ids=[self.example_email("hamlet")]
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
        result = generic_bulk_cached_fetch(
            cache_key_function=cache_key_function,
            query_function=query_function,
            object_ids=[]
        )  # type: Dict[str, UserProfile]
        self.assertEqual(result, {})
