import unittest
from django.contrib.auth.models import User
from django.utils.translation import activate
from zerver.lib.translate import translate_message
from zerver.actions.create_user import do_create_user
from zerver.models import Realm


class MessageTranslationTestCase(unittest.TestCase):
    def test_send_translated_message(self):
        # Create a user with a preferred language
        realm = Realm.objects.get(string_id='zulip')
        user = do_create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )
        user.user_preferred_language = 'es'
        user.save()

        # Activate the user's preferred language
        activate(user.user_preferred_language)

        # Translate a message content using the user's preferred language
        translated_content = translate_message('good morning', user.user_preferred_language)

        # Assert that the message has been translated correctly
        self.assertEqual(translated_content, 'buenos días')


if __name__ == '__main__':
    unittest.main()
