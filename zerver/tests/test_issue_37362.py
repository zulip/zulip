from zerver.lib.test_classes import ZulipTestCase
from zerver.models import PreregistrationUser, RealmAuditLog, MultiuseInvite, Realm
from confirmation.models import Confirmation
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.actions.invites import do_revoke_user_invite, do_revoke_multi_use_invite, do_get_invites_controlled_by_user
from confirmation import settings as confirmation_settings
from django.utils.timezone import now as timezone_now

class RevokeInviteTest(ZulipTestCase):
    def test_revoke_invites(self) -> None:
        user_profile = self.example_user("iago") # Admin
        realm = user_profile.realm
        email = "test_revoke_single@example.com"
        
        # 1. Test Single User Invite Revocation
        prereg_user = PreregistrationUser.objects.create(
            email=email,
            realm=realm,
            referred_by=user_profile,
            status=0
        )
        Confirmation.objects.create(
            content_object=prereg_user,
            date_sent=timezone_now(),
            confirmation_key="test_single_key",
            type=Confirmation.INVITATION
        )
        
        do_revoke_user_invite(prereg_user, acting_user=user_profile)
        
        prereg_user.refresh_from_db()
        self.assertEqual(prereg_user.status, confirmation_settings.STATUS_REVOKED)
        self.assertTrue(Confirmation.objects.filter(confirmation_key="test_single_key").exists())
        
        self.assertTrue(RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.USER_INVITATION_REVOKED,
            extra_data__contains={"prereg_user_id": prereg_user.id}
        ).exists())

        # 2. Test Multiuse Invite Revocation
        multi_invite = MultiuseInvite.objects.create(
            realm=realm,
            referred_by=user_profile,
            status=0
        )
        conf_multi = Confirmation.objects.create(
            content_object=multi_invite,
            date_sent=timezone_now(),
            confirmation_key="test_multi_key",
            type=Confirmation.MULTIUSE_INVITE
        )
        
        do_revoke_multi_use_invite(multi_invite, acting_user=user_profile)
        
        multi_invite.refresh_from_db()
        self.assertEqual(multi_invite.status, confirmation_settings.STATUS_REVOKED)
        self.assertTrue(Confirmation.objects.filter(confirmation_key="test_multi_key").exists())

        self.assertTrue(RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.USER_INVITATION_REVOKED,
            extra_data__contains={"multiuse_invite_id": multi_invite.id}
        ).exists())
        
        # 3. Test Retrieve Invites (Regression Check)
        # This function should not crash and should exclude the revoked multiuse invite
        invites = do_get_invites_controlled_by_user(user_profile)
        
        # Check that the revoked multiuse invite is NOT in the list
        found_revoked = any(i.get('id') == multi_invite.id and i.get('is_multiuse') for i in invites)
        self.assertFalse(found_revoked, "Revoked multiuse invite should not be returned in controlled invites list")
