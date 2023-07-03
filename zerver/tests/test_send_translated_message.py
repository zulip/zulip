import unittest
from zerver.models import UserProfile
from django.utils.translation import activate
from zerver.lib.translate import translate_message

from zerver.actions.create_user import do_create_user
from zerver.models import Realm


class MessageTranslationTestCase(unittest.TestCase):
    def test_send_message_translation(self):
        realm = Realm.objects.get(string_id='zulip')  # Get the realm
        self.user = do_create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )

        # Translate the message content using the user's preferred language
        translated_content = translate_message("good morning", self.user.user_preferred_language)

        # Assert that the message content has been translated correctly
        self.assertEqual(translated_content, 'bonjour')


if __name__ == '__main__':
    unittest.main()
