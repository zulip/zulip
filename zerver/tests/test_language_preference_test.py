from django.test import RequestFactory, TestCase
from django.contrib.auth.models import User
from zerver.middleware import SetUserPreferredLanguageMiddleware

class SetUserPreferredLanguageMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SetUserPreferredLanguageMiddleware(lambda r: None)

    def test_set_user_preferred_language(self):
        # Create a user
        user = User.objects.create_user(username='testuser', password='testpassword')

        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'en-US,en;q=0.9'

        # Set the user on the request
        request.user = user

        # Call the middleware
        self.middleware(request)

        # Refresh the user from the database
        user.refresh_from_db()

        # Assert that the user's user_preferred_language field is set correctly
        self.assertEqual(user.user_preferred_language, 'en-US')

    def test_set_user_preferred_language_no_user(self):
        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'en-US,en;q=0.9'

 # Call the middleware
        self.middleware(request)

        # Assert that the user_preferred_language field is not set
        self.assertFalse(hasattr(request.user, 'user_preferred_language'))
