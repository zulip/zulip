from django.contrib.auth.models import User
from django.conf import settings
from zephyr.lib.cache import cache_with_key

@cache_with_key(lambda user_id: 'tornado_user:%d' % (user_id,))
def get_tornado_user(user_id):
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
        if settings.RUNNING_INSIDE_TORNADO:
            # Get the User from a cache because we aren't accessing
            # any mutable fields from Tornado (just the id)
            return get_tornado_user(user_id)
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
