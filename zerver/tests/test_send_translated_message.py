import unittest
from django.contrib.auth.models import User
from django.utils.translation import activate
from zerver.lib.message import SendMessageRequest
from zerver.lib.translate import translate_message
from zerver.models import Realm

from zerver.actions.create_user import do_create_user


class TranslateMessageTestCase(unittest.TestCase):
    def test_translate_message_content(self):
        # Create a sender with a preferred language
        realm = Realm.objects.get(string_id='zulip')  # Get the realm
        sender = do_create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )

        sender.user_preferred_language = 'es'
        sender.save()

        # Create a send_message_request with a message content
        send_message_request = SendMessageRequest(sender=sender, message_content='Hello')

        # Activate the sender's preferred language
        activate(sender.user_preferred_language)

        # Translate the message content using the sender's preferred language
        translated_content = translate_message(send_message_request.message_content,
                                               sender.user_preferred_language)

        # Update the message content with the translated text
        send_message_request.message_content = translated_content

        # Assert that the message content has been translated correctly
        self.assertEqual(send_message_request.message_content, 'Hola')


if __name__ == '__main__':
    unittest.main()
