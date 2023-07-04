from django.test import RequestFactory, TestCase, override_settings

from zerver.middleware import SetUserPreferredLanguageMiddleware

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
            email='user1@zulip.com',
            password='password',
            realm=realm,
            full_name='User',
            acting_user=None
        )
        # Create a request with the HTTP_ACCEPT_LANGUAGE header
        request = self.factory.get('/')
        request.META['HTTP_ACCEPT_LANGUAGE'] = 'fr'

        # Set the user on the request
        request.user = self.user

        # Call the middleware
        self.middleware(request)

        # Refresh the user from the database
        self.user.refresh_from_db()

        preferred_language = self.user.user_preferred_language
        print(preferred_language)  # Print the value on console
        # Assert that the user's user_preferred_language field is set correctly
        self.assertEqual(preferred_language, 'fr')


