"""
Implements the per-domain data retention policy.

The goal is to have a single place where the policy is defined.  This is
complicated by needing to apply this policy both to the database and to log
files.  Additionally, we want to use an efficient query for the database,
rather than iterating through messages one by one.

The code in this module does not actually remove anything; it just identifies
which items should be kept or removed.
"""

import sys
import operator

from django.utils     import timezone
from django.db.models import Q
from datetime         import datetime, timedelta
from zephyr.models    import Realm, UserMessage

# Each domain has a maximum age for retained messages.
#
# FIXME: Move this into the database.
max_age = {
    'customer1.invalid': timedelta(days=31),
}

def should_expunge_from_log(msg, now):
    """Should a particular log entry be expunged?

       msg: a log entry dict
       now: current time for purposes of determining log entry age"""

    # This function will be called many times, but we want to compare all
    # entries against a consistent "current time".  So the caller passes
    # that time as a parameter.

    if msg.get('type') in ('default_streams', 'realm_created'):
        # These don't have an associated user.
        # We could use the 'domain' field, but it probably makes sense to
        # keep these forever.
        return False

    # FIXME: Yet another place where we compute the domain manually.
    # See #260.
    user = msg.get('sender_email')
    if user is None:
        user = msg.get('user')
    if user is None:
        # Avoid printing the entire message, but give enough information to find it later.
        # Print the repr of the timestamp; otherwise it gets rounded!
        print >>sys.stderr, "WARNING: Can't get user for entry at", repr(msg['timestamp'])
        return False
    domain = user.split('@', 1)[1]

    if domain not in max_age:
        # Keep forever.
        return False

    age = now - datetime.fromtimestamp(msg['timestamp'])
    return age > max_age[domain]

def get_UserMessages_to_expunge():
    """Fetch all UserMessages which should be expunged from the database.

       After deleting these, you may also want to call
       Message.remove_unreachable()."""
    # Unlike retain_in_log, this handles all messages at once, so we
    # use the actual current time.
    now = timezone.now()
    queries = [Q(user_profile__realm   = realm,
                 message__pub_date__lt = now - max_age[realm.domain])
               for realm in Realm.objects.all()
               if  realm.domain in max_age]

    if not queries:
        return UserMessage.objects.none()

    # Return all objects matching any of the queries in 'queries'.
    return UserMessage.objects.filter(reduce(operator.or_, queries))
