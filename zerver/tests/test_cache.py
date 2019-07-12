from django.conf import settings

from mock import Mock, patch

from zerver.apps import flush_cache
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_system_bot, get_user_profile_by_email

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
