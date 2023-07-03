import unittest
from django.contrib.auth.models import User
from django.utils.translation import activate
from zerver.lib.translate import translate_message


class MessageTranslationTestCase(unittest.TestCase):
    def test_send_translated_message(self):
        user = User.objects.create(
            username='test',
            user_preferred_language='es'
        )

        # Activate the user's preferred language
        activate(user.user_preferred_language)

        # Translate a message content using the user's preferred language
        translated_content = translate_message('good morning', user.user_preferred_language)

        # Assert that the message has been translated correctly
        self.assertEqual(translated_content, 'buenos días')


if __name__ == '__main__':
    unittest.main()
