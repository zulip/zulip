from django.test import RequestFactory, TestCase
from zerver.middleware import SetUserPreferredLanguageMiddleware


from zerver.models import UserProfile

from zerver.models import Realm


class SetUserPreferredLanguageMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SetUserPreferredLanguageMiddleware(lambda r: None)

    def test_set_user_preferred_language(self):
        # Create a user
        realm = Realm.objects.get(string_id='zulip')

        user = UserProfile.objects.create(
            email='test@example.com',
            realm=realm
        )
        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'fr'

        # Set the user on the request
        request.user = user

        # Call the middleware
        self.middleware(request)

        # Refresh the user from the database
        user.refresh_from_db()
        print(user.preferred_language)

        # Assert that the user's preferred_language field is set correctly
        self.assertEqual(user.preferred_language, 'fr')


