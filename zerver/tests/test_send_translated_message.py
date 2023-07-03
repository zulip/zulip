import unittest

from zerver.lib.translate import translate_message

from zerver.models import Realm, UserProfile

from django.test import Client


class MessageTranslationTestCase(unittest.TestCase):

    @staticmethod
    def create_user(self, preferred_language):
        realm = Realm.objects.get(string_id='zulip')
        return UserProfile.objects.create(
            email='test@example.com',
            user_preferred_language=preferred_language,
            realm=realm
        )

    def login_user(self, user_profile):
        self.client = Client()

        logged_in = self.client.login(username=user_profile.email, password='testpassword')
        self.assertTrue(logged_in)

    def test_send_message_translation(self):
        user_profile = self.create_user('es')
        self.login_user(user_profile)

        # Rest of the test case...

        preferred_language = user_profile.user_preferred_language

        # Translate a message content using the user's preferred language
        translated_content = translate_message('good morning', preferred_language)

        # Assert that the message has been translated correctly
        self.assertEqual(translated_content, 'buenos días')


if __name__ == '__main__':
    unittest.main()
