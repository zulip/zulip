from typing import List, Optional

from django.db.models import Q
from django.utils.timezone import now as timezone_now

from confirmation.models import Confirmation
from zerver.models import MultiuseInvite, PreregistrationUser, Realm, UserProfile
from zerver.models.prereg_users import filter_to_valid_prereg_users
from zerver.tornado.django_api import send_event_on_commit


def notify_invites_changed(
    realm: Realm, *, changed_invite_referrer: Optional[UserProfile] = None
) -> None:
    event = dict(type="invites_changed")
    admin_ids = [user.id for user in realm.get_admin_users_and_bots()]
    recipient_ids = admin_ids
    if changed_invite_referrer and changed_invite_referrer.id not in recipient_ids:
        recipient_ids.append(changed_invite_referrer.id)
    send_event_on_commit(realm, event, recipient_ids)


def get_valid_invite_confirmations_generated_by_user(
    user_profile: UserProfile,
) -> List[Confirmation]:
    prereg_user_ids = filter_to_valid_prereg_users(
        PreregistrationUser.objects.filter(referred_by=user_profile)
    ).values_list("id", flat=True)
    confirmations = list(
        Confirmation.objects.filter(type=Confirmation.INVITATION, object_id__in=prereg_user_ids)
    )

    multiuse_invite_ids = MultiuseInvite.objects.filter(referred_by=user_profile).values_list(
        "id", flat=True
    )
    confirmations += Confirmation.objects.filter(
        type=Confirmation.MULTIUSE_INVITE,
        object_id__in=multiuse_invite_ids,
    ).filter(Q(expiry_date__gte=timezone_now()) | Q(expiry_date=None))

    return confirmations


def revoke_invites_generated_by_user(user_profile: UserProfile) -> None:
    confirmations_to_revoke = get_valid_invite_confirmations_generated_by_user(user_profile)
    now = timezone_now()
    for confirmation in confirmations_to_revoke:
        confirmation.expiry_date = now

    Confirmation.objects.bulk_update(confirmations_to_revoke, ["expiry_date"])
    if len(confirmations_to_revoke):
        notify_invites_changed(realm=user_profile.realm)
