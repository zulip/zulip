import unittest
from unittest.mock import patch
from django.contrib.auth.models import User
from django.utils.translation import activate
from zerver.translate translate_message
from zerver.actions.create_user import do_create_user
from zerver.models import Realm

class MessageSendTestCase(unittest.TestCase):
    @patch('path.to.SendMessageRequest')  # Replace 'path.to' with the actual import path of SendMessageRequest
    def test_send_message_translation(self, mock_send_message_request):
        # Create a sender a preferred language
        realm = Realm.objects.get(string_id='zulip')  # Get the realm
        sender = do_create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )

        sender.user_preferred_language = 'fr'
        sender.save        # Create a mock object for SendMessageRequest
        send_message_request = mock_send_message_request.return_value
        send_message_request.sender = sender
        send_message_request.message_content = 'good morning'

        # Activate the sender's preferred language
        activate(sender.user_preferred_language)

        # Translate the message content using the sender's preferred language
        translated_content = translate_message(send_message_request.message_content, sender.user_preferred_language)

        # Update the message content with the translated text
        send_message_request.message_content = translated_content

        # Verify that the translated message is included in the message payload
        self.assertEqual(send_message_request.message_content, 'bonjour')

if __name__ == '__main__':
    unittest.main()
