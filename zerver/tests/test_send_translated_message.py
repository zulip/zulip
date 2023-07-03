import unittest
from zerver.lib.translate import translate_message


class MessageTranslationTestCase(unittest.TestCase):
    def test_send_message_translation(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        preferred_language = user_profile.user_preferred_language

        # Translate a message content using the user's preferred language
        translated_content = translate_message('good morning', preferred_language)

        # Assert that the message has been translated correctly
        self.assertEqual(translated_content, 'buenos días')


if __name__ == '__main__':
    unittest.main()
