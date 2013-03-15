from django.contrib.auth.models import User
from django.conf import settings

from openid.consumer.consumer import SUCCESS

from zephyr.lib.cache import cache_with_key
from zephyr.lib.cache import user_by_id_cache_key

@cache_with_key(user_by_id_cache_key)
def get_user_by_id(user_id):
    try:
        return User.objects.select_related().get(id=user_id)
    except User.DoesNotExist:
        return None

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
            user = User.objects.get(email__iexact=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        """ Get a User object from the user_id. """
        return get_user_by_id(user_id)

# Adapted from http://djangosnippets.org/snippets/2183/ by user Hangya (September 1, 2010)

class GoogleBackend:
    def authenticate(self, openid_response):
        if openid_response is None:
            return None
        if openid_response.status != SUCCESS:
            return None

        google_email = openid_response.getSigned('http://openid.net/srv/ax/1.0', 'value.email')

        try:
            user = User.objects.get(email__iexact=google_email)
        except User.DoesNotExist:
            # create a new user, or send a message to admins, etc.
            return None

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
