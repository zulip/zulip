from django.test import TestCase
from django.contrib.auth import get_user_model
from django.test.client import RequestFactory

from zerver.middleware import *

from zulip.zerver.models import Realm


class SetUserPreferredLanguageMiddlewareTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SetUserPreferredLanguageMiddleware(lambda r: None)

    def test_set_user_preferred_language(self):
        # Create a user
        realm = Realm.objects.get(string_id='zulip')  # Get the realm
        user = get_user_model().objects.create_user(
            email='user@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )

        # Create a request with the user
        request = self.factory.get('/')
        request.user = user

        # Set the 'Accept-Language' header to a specific language
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'en-US'

        # Call the middleware
        self.middleware(request)

        # Refresh the user from the database
        user.refresh_from_db()

        # Assert that the user's user_preferred_language field is updated
        self.assertEqual(user.user_preferred_language, 'en-US')
