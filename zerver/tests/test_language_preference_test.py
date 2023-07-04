from django.test import RequestFactory, TestCase
from zerver.middleware import SetUserPreferredLanguageMiddleware


from zerver.models import UserProfile


class SetUserPreferredLanguageMiddlewareTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SetUserPreferredLanguageMiddleware(lambda r: None)

    def test_set_user_preferred_language(self):
        # Create a user
        user = UserProfile.objects.create(email='test@example.com')

        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'fr'

        # Set the user on the request
        request.user = user

        # Call the middleware
        self.middleware(request)

        # Refresh the user from the database
        user.refresh_from_db()

        # Assert that the user's preferred_language field is set correctly
        self.assertEqual(user.preferred_language, 'fr')

    def test_set_user_preferred_language_no_user(self):
        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')

        # Call the middleware
        self.middleware(request)

        # Assert that the preferred_language field is not set
        self.assertFalse(hasattr(request.user, 'preferred_language'))
