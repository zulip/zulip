import unittest
from zerver.models import UserProfile
from django.utils.translation import activate
from zerver.lib.translate import translate_message


class MessageTranslationTestCase(unittest.TestCase):
    def test_send_message_translation(self):
        # Create a user profile with a preferred language
        user_profile = UserProfile.objects.create_user(
            email='testuser@example.com',
            password='testpassword',
            user_preferred_language='fr'
        )

        # Translate the message content using the user's preferred language
        translated_content = translate_message("good morning", user_profile.user_preferred_language)

        # Assert that the message content has been translated correctly
        self.assertEqual(translated_content, 'bonjour')


if __name__ == '__main__':
    unittest.main()
