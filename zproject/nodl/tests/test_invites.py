import hashlib
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zproject.nodl.models import NodlInvite
from zproject.nodl.views.invites import mark_invite_registered


class NodlInviteModelTest(TestCase):
    """Tests for the NodlInvite model."""

    def setUp(self) -> None:
        self.user = UserProfile.objects.filter(is_active=True).first()
        assert self.user is not None

    def test_computed_status_sent(self) -> None:
        invite = NodlInvite.objects.create(
            inviter=self.user,
            invited_phone_hash="a" * 64,
            invited_phone_display="***1234",
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(invite.computed_status, "sent")

    def test_computed_status_expired(self) -> None:
        invite = NodlInvite.objects.create(
            inviter=self.user,
            invited_phone_hash="b" * 64,
            invited_phone_display="***5678",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertEqual(invite.computed_status, "expired")

    def test_computed_status_registered(self) -> None:
        invite = NodlInvite.objects.create(
            inviter=self.user,
            invited_phone_hash="c" * 64,
            invited_phone_display="***9999",
            invited_user=self.user,  # self-referential for test simplicity
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertEqual(invite.computed_status, "registered")

    def test_to_api_dict(self) -> None:
        invite = NodlInvite.objects.create(
            inviter=self.user,
            invited_phone_hash="d" * 64,
            invited_phone_display="***0000",
            expires_at=timezone.now() + timedelta(days=7),
        )
        api = invite.to_api_dict()
        self.assertEqual(api["phone_display"], "***0000")
        self.assertEqual(api["status"], "sent")
        self.assertIsNone(api["invited_name"])
        self.assertIn("created_at", api)
        self.assertIn("expires_at", api)


class NodlInviteViewsTest(ZulipTestCase):
    """Tests for invite API endpoints."""

    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")

    def _auth_headers(self) -> dict[str, str]:
        import base64

        cred = base64.b64encode(f"{self.user.delivery_email}:{self.user.api_key}".encode()).decode()
        return {"HTTP_AUTHORIZATION": f"Basic {cred}"}

    def test_invites_list_empty(self) -> None:
        result = self.client_get("/nodl/invites", **self._auth_headers())
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["invites"], [])

    def test_invites_create_and_list(self) -> None:
        # Create an invite
        result = self.client_post(
            "/nodl/invites/create",
            json.dumps({"phone_hash": "e" * 64, "phone_display": "***1234"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["invite"]["phone_display"], "***1234")
        self.assertEqual(data["invite"]["status"], "sent")

        # List and verify
        result = self.client_get("/nodl/invites", **self._auth_headers())
        data = result.json()
        self.assertEqual(len(data["invites"]), 1)

    def test_invites_create_invalid_hash(self) -> None:
        result = self.client_post(
            "/nodl/invites/create",
            json.dumps({"phone_hash": "tooshort", "phone_display": "***1234"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)

    def test_invites_resend(self) -> None:
        invite = NodlInvite.objects.create(
            inviter=self.user,
            invited_phone_hash="f" * 64,
            invited_phone_display="***5678",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertEqual(invite.computed_status, "expired")

        result = self.client_post(
            "/nodl/invites/resend",
            json.dumps({"invite_id": invite.pk}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["invite"]["status"], "sent")

    def test_invites_resend_not_found(self) -> None:
        result = self.client_post(
            "/nodl/invites/resend",
            json.dumps({"invite_id": 99999}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 404)

    def test_invites_unauthorized(self) -> None:
        result = self.client_get("/nodl/invites")
        self.assertEqual(result.status_code, 401)


class MarkInviteRegisteredTest(TestCase):
    """Tests for the mark_invite_registered helper."""

    def setUp(self) -> None:
        self.inviter = UserProfile.objects.filter(is_active=True).first()
        assert self.inviter is not None
        # Get a different user for the invitee
        self.invitee = (
            UserProfile.objects.filter(is_active=True).exclude(pk=self.inviter.pk).first()
        )
        assert self.invitee is not None

    def test_marks_matching_invite(self) -> None:
        phone_hash = hashlib.sha256(b"+15551234567").hexdigest()
        invite = NodlInvite.objects.create(
            inviter=self.inviter,
            invited_phone_hash=phone_hash,
            invited_phone_display="***4567",
            expires_at=timezone.now() + timedelta(days=7),
        )

        mark_invite_registered(phone_hash, self.invitee)
        invite.refresh_from_db()
        self.assertEqual(invite.invited_user, self.invitee)
        self.assertEqual(invite.computed_status, "registered")

    def test_ignores_non_matching_hash(self) -> None:
        invite = NodlInvite.objects.create(
            inviter=self.inviter,
            invited_phone_hash="a" * 64,
            invited_phone_display="***0000",
            expires_at=timezone.now() + timedelta(days=7),
        )

        mark_invite_registered("b" * 64, self.invitee)
        invite.refresh_from_db()
        self.assertIsNone(invite.invited_user)

    def test_ignores_already_registered(self) -> None:
        phone_hash = hashlib.sha256(b"+15559876543").hexdigest()
        invite = NodlInvite.objects.create(
            inviter=self.inviter,
            invited_phone_hash=phone_hash,
            invited_phone_display="***6543",
            invited_user=self.inviter,  # already registered
            expires_at=timezone.now() + timedelta(days=7),
        )

        mark_invite_registered(phone_hash, self.invitee)
        invite.refresh_from_db()
        # Should still be the original user, not overwritten
        self.assertEqual(invite.invited_user, self.inviter)
