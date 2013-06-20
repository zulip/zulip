from zephyr.models import UserProfile, get_user_profile_by_id, \
    get_user_profile_by_email
from django.conf import settings

from openid.consumer.consumer import SUCCESS

class EmailAuthBackend(object):
    """
    Email Authentication Backend

    Allows a user to sign in using an email/password pair rather than
    a username/password pair.
    """

    def authenticate(self, username=None, password=None):
        """ Authenticate a user based on email address as the user name. """
        if username is None or password is None:
            # Return immediately.  Otherwise we will look for a SQL row with
            # NULL username.  While that's probably harmless, it's needless
            # exposure.
            return None

        try:
            user_profile = get_user_profile_by_email(username)
            if user_profile.check_password(password):
                return user_profile
        except UserProfile.DoesNotExist:
            return None

    def get_user(self, user_profile_id):
        """ Get a UserProfile object from the user_profile_id. """
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            return None

# Adapted from http://djangosnippets.org/snippets/2183/ by user Hangya (September 1, 2010)

class GoogleBackend(object):
    def authenticate(self, openid_response):
        if openid_response is None:
            return None
        if openid_response.status != SUCCESS:
            return None

        google_email = openid_response.getSigned('http://openid.net/srv/ax/1.0', 'value.email')

        try:
            user_profile = get_user_profile_by_email(google_email)
        except UserProfile.DoesNotExist:
            # create a new user, or send a message to admins, etc.
            return None

        return user_profile

    def get_user(self, user_profile_id):
        """ Get a UserProfile object from the user_profile_id. """
        try:
            return get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            return None
