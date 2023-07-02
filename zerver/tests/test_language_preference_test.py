from django.test import TestCase, Client
from unittest.mock import patch
from zerver.actions.create_user import do_create_user
from zerver.models import UserProfile, Realm
from django.test.utils import override_settings
from zerver.middleware import *

MIDDLEWARE_CLASSES = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'zerver.middleware.UserPreferredLanguageMiddleware',
]

@override_settings(MIDDLEWARE=MIDDLEWARE_CLASSES)
class LanguagePreferenceTestCase(TestCase):
    def setUp(self):
        # Mock the do_send_messages function
        with patch('zerver.actions.message_send.do_send_messages'):
            # Create a test user
            realm = Realm.objects.get(string_id='zulip')  # Get the realm
            self.user = do_create_user(
                email='user@zulip.com',
                password='password',
                realm=realm,
                full_name='User',
                acting_user=None
            )
        self.client = Client()

    def test_language_preference(self):
        # Log in the test user
        self.client.login(username='user@zulip.com', password='password')

        # Send a request with a specific Accept-Language header
        self.client.get(reverse('home'), HTTP_ACCEPT_LANGUAGE='fr')

        # Reload the user object from the database
        self.user = UserProfile(email='user@zulip.com')

        # Check if the user's preferred language was updated correctly
        self.assertEqual(self.user.preferred_language, 'fr')
