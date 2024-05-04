from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import CASCADE, Q, QuerySet
from django.db.models.functions import Upper
from django.utils.timezone import now as timezone_now

from confirmation import settings as confirmation_settings
from zerver.models.constants import MAX_LANGUAGE_ID_LENGTH
from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class PreregistrationRealm(models.Model):
    """Data on a partially created realm entered by a user who has
    completed the "new organization" form. Used to transfer the user's
    selections from the pre-confirmation "new organization" form to
    the post-confirmation user registration form.

    Note that the values stored here may not match those of the
    created realm (in the event the user creates a realm at all),
    because we allow the user to edit these values in the registration
    form (and in fact the user will be required to do so if the
    `string_id` is claimed by another realm before registraiton is
    completed).
    """

    name = models.CharField(max_length=Realm.MAX_REALM_NAME_LENGTH)
    org_type = models.PositiveSmallIntegerField(
        default=Realm.ORG_TYPES["unspecified"]["id"],
        choices=[(t["id"], t["name"]) for t in Realm.ORG_TYPES.values()],
    )
    default_language = models.CharField(
        default="en",
        max_length=MAX_LANGUAGE_ID_LENGTH,
    )
    string_id = models.CharField(max_length=Realm.MAX_REALM_SUBDOMAIN_LENGTH)
    email = models.EmailField()

    confirmation = GenericRelation("confirmation.Confirmation", related_query_name="prereg_realm")
    status = models.IntegerField(default=0)

    # The Realm created upon completion of the registration
    # for this PregistrationRealm
    created_realm = models.ForeignKey(Realm, null=True, related_name="+", on_delete=models.SET_NULL)

    # The UserProfile created upon completion of the registration
    # for this PregistrationRealm
    created_user = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=models.SET_NULL
    )


class PreregistrationUser(models.Model):
    # Data on a partially created user, before the completion of
    # registration.  This is used in at least three major code paths:
    # * Realm creation, in which case realm is None.
    #
    # * Invitations, in which case referred_by will always be set.
    #
    # * Social authentication signup, where it's used to store data
    #   from the authentication step and pass it to the registration
    #   form.

    email = models.EmailField()

    confirmation = GenericRelation("confirmation.Confirmation", related_query_name="prereg_user")
    # If the pre-registration process provides a suggested full name for this user,
    # store it here to use it to prepopulate the full name field in the registration form:
    full_name = models.CharField(max_length=UserProfile.MAX_NAME_LENGTH, null=True)
    full_name_validated = models.BooleanField(default=False)
    referred_by = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)
    streams = models.ManyToManyField("zerver.Stream")
    invited_at = models.DateTimeField(auto_now=True)
    realm_creation = models.BooleanField(default=False)
    # Indicates whether the user needs a password.  Users who were
    # created via SSO style auth (e.g. GitHub/Google) generally do not.
    password_required = models.BooleanField(default=True)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    # The realm should only ever be None for PreregistrationUser
    # objects created as part of realm creation.
    realm = models.ForeignKey(Realm, null=True, on_delete=CASCADE)

    # These values should be consistent with the values
    # in settings_config.user_role_values.
    INVITE_AS = dict(
        REALM_OWNER=100,
        REALM_ADMIN=200,
        MODERATOR=300,
        MEMBER=400,
        GUEST_USER=600,
    )
    invited_as = models.PositiveSmallIntegerField(default=INVITE_AS["MEMBER"])

    multiuse_invite = models.ForeignKey("MultiuseInvite", null=True, on_delete=models.SET_NULL)

    # The UserProfile created upon completion of the registration
    # for this PregistrationUser
    created_user = models.ForeignKey(
        UserProfile, null=True, related_name="+", on_delete=models.SET_NULL
    )

    class Meta:
        indexes = [
            models.Index(Upper("email"), name="upper_preregistration_email_idx"),
        ]


def filter_to_valid_prereg_users(
    query: QuerySet[PreregistrationUser],
) -> QuerySet[PreregistrationUser]:
    """
    If invite_expires_in_days is specified, we return only those PreregistrationUser
    objects that were created at most that many days in the past.
    """
    used_value = confirmation_settings.STATUS_USED
    revoked_value = confirmation_settings.STATUS_REVOKED

    query = query.exclude(status__in=[used_value, revoked_value])
    return query.filter(
        Q(confirmation__expiry_date=None) | Q(confirmation__expiry_date__gte=timezone_now())
    )


class MultiuseInvite(models.Model):
    referred_by = models.ForeignKey(UserProfile, on_delete=CASCADE)
    streams = models.ManyToManyField("zerver.Stream")
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    invited_as = models.PositiveSmallIntegerField(default=PreregistrationUser.INVITE_AS["MEMBER"])

    # status for tracking whether the invite has been revoked.
    # If revoked, set to confirmation.settings.STATUS_REVOKED.
    # STATUS_USED is not supported, because these objects are supposed
    # to be usable multiple times.
    status = models.IntegerField(default=0)


class EmailChangeStatus(models.Model):
    new_email = models.EmailField()
    old_email = models.EmailField()
    updated_at = models.DateTimeField(auto_now=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)


class RealmReactivationStatus(models.Model):
    # status: whether an object has been confirmed.
    #   if confirmed, set to confirmation.settings.STATUS_USED
    status = models.IntegerField(default=0)

    realm = models.ForeignKey(Realm, on_delete=CASCADE)
