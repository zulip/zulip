from django.utils.timezone import now as timezone_now

from zerver.lib.followed_users import add_user_follow, get_user_follows, get_follow_object
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def do_follow_user(user_profile: UserProfile, followed_user: UserProfile) -> None:
    add_user_follow(user_profile, followed_user, timezone_now())
    event = dict(type="followed_users", followed_users=get_user_follows(user_profile))
    send_event_on_commit(user_profile.realm, event, [user_profile.id])


def do_unfollow_user(user_profile: UserProfile, followed_user: UserProfile) -> None:
    follow_object = get_follow_object(user_profile, followed_user)
    if follow_object:
        follow_object.delete()
    event = dict(type="followed_users", followed_users=get_user_follows(user_profile))
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
