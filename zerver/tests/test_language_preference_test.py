from django.test import RequestFactory, TestCase, override_settings
from django.contrib.auth.models import User
from zerver.middleware import SetUserPreferredLanguageMiddleware
from django.contrib.auth import get_user_model

from zerver.models import Realm

from zerver.actions.create_user import do_create_user


class SetUserPreferredLanguageMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SetUserPreferredLanguageMiddleware(lambda r: None)

    def test_set_user_preferred_language(self):

        # Create a user
        realm = Realm.objects.get(string_id='zulip')  # Get the realm
        self.user = do_create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )
        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'en-US'

        # Set the user on the request
        request.user = self.user

        # Call the middleware
        self.middleware(request)

        # Refresh the user from the database
        self.user.refresh_from_db()

        # Assert that the user's user_preferred_language field is set correctly
        self.assertEqual(self.user.user_preferred_language, 'en-US')

    def test_set_user_preferred_language_no_user(self):
        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'en-US'

        # Call the middleware
        self.middleware(request)

        # Assert that the user_preferred_language field is not set
        self.assertFalse(hasattr(request.user, 'user_preferred_language'))
