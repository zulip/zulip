"""
Implements the per-domain data retention policy.

The goal is to have a single place where the policy is defined.  This is
complicated by needing to apply this policy both to the database and to log
files.  Additionally, we want to use an efficient query for the database,
rather than iterating through messages one by one.

The code in this module does not actually remove anything; it just identifies
which items should be kept or removed.
"""
from __future__ import absolute_import

import operator

from django.utils     import timezone
from django.db.models import Q
from datetime         import datetime, timedelta
from zerver.models    import Realm, UserMessage, get_user_profile_by_email

# Each domain has a maximum age for retained messages.
#
# FIXME: Move this into the database.
max_age = {
    'customer1.invalid': timedelta(days=31),
}

domain_cache = {}

def should_expunge_from_log(msg, now):
    """Should a particular log entry be expunged?

       msg: a log entry dict
       now: current time for purposes of determining log entry age"""

    # This function will be called many times, but we want to compare all
    # entries against a consistent "current time".  So the caller passes
    # that time as a parameter.

    if msg.get('type') not in ('stream', 'huddle', 'personal'):
        # Keep all metadata changes like realm_created, subscription_added,
        # etc.
        return False

    user_email = msg['sender_email']
    domain = domain_cache.get(user_email)
    if not domain:
        domain = get_user_profile_by_email(user_email).realm.domain
        domain_cache[user_email] = domain

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
