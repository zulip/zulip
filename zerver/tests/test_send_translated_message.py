import unittest

from zerver.lib.translate import translate_message

from zerver.models import Realm, UserProfile

from django.test import Client

from zerver.actions.create_user import do_create_user


class MessageTranslationTestCase(unittest.TestCase):

    def create_user(self, preferred_language):
        realm = Realm.objects.get(string_id='zulip')
        self.user = do_create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )

        self.user.user_preferred_language = preferred_language
        self.user.save()
        return self.user

    def login_user(self, user_profile):
        user_profile.set_password('testpassword')
        user_profile.save()

        self.client = Client()
        try:
            logged_in = self.client.login(username=user_profile.email, password='testpassword')
        except Exception as e:
            print(e)
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
