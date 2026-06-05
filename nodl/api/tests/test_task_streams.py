"""Unit tests for internal task stream endpoints."""

import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from nodl.api.views.task_streams import (
    TaskStreamMemberPayload,
    _resolve_realm_user,
    archive_task_stream,
    sync_task_stream,
    sync_task_stream_subscribers,
)


class TestTaskStreamAuth(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_service_auth_required(self) -> None:
        request = self.factory.post("/api/v1/internal/task-streams/sync")
        request.is_service_request = False

        response = sync_task_stream(request)

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "UNAUTHORIZED")


class TestTaskStreamSync(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.workspace_id = str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        self.payload = {
            "workspace_id": self.workspace_id,
            "task_id": self.task_id,
            "stream_name": f"task-{self.task_id}",
            "privacy_tag": "internal",
            "members": [
                {
                    "supabase_user_id": str(uuid.uuid4()),
                    "email": "person@example.com",
                    "full_name": "Person",
                    "avatar_url": None,
                    "role": "assignee",
                }
            ],
        }

    def _request(self, payload: dict):
        request = self.factory.post(
            "/api/v1/internal/task-streams/sync",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.is_service_request = True
        return request

    @patch("nodl.api.views.task_streams._set_task_subscription_preferences")
    @patch("nodl.api.views.task_streams.bulk_add_subscriptions")
    @patch("nodl.api.views.task_streams._resolve_members")
    @patch("nodl.api.views.task_streams.create_stream_if_needed")
    @patch("nodl.api.views.task_streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.task_streams._get_realm")
    def test_sync_creates_private_stream_once(
        self,
        mock_get_realm: MagicMock,
        mock_extension_objects: MagicMock,
        mock_create_stream: MagicMock,
        mock_resolve_members: MagicMock,
        mock_subscribe: MagicMock,
        mock_preferences: MagicMock,
    ) -> None:
        realm = MagicMock(id=1)
        stream = MagicMock(id=42, name=self.payload["stream_name"])
        mock_get_realm.return_value = realm
        extension_lookup = mock_extension_objects.select_related.return_value.filter.return_value
        extension_lookup.first.return_value = None
        mock_create_stream.return_value = (stream, True)
        user = MagicMock(id=5, realm_id=1)
        mock_resolve_members.return_value = [user]

        response = sync_task_stream(self._request(self.payload))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["zulip_stream_id"], 42)
        mock_create_stream.assert_called_once()
        self.assertTrue(mock_create_stream.call_args.kwargs["invite_only"])
        mock_extension_objects.create.assert_called_once()
        mock_subscribe.assert_called_once()
        mock_preferences.assert_called_once_with(stream, [user])

    @patch("nodl.api.views.task_streams.NodlRealmUserExtension.objects")
    @patch("nodl.api.views.task_streams.NodlUserExtension.objects")
    @patch("nodl.api.views.task_streams.UserProfile.objects")
    def test_resolve_realm_user_uses_realm_scoped_lookup_without_rehoming_global(
        self,
        mock_user_objects: MagicMock,
        mock_global_extension_objects: MagicMock,
        mock_realm_user_objects: MagicMock,
    ) -> None:
        realm = MagicMock(id=10)
        user = MagicMock(id=99, realm_id=10)
        member = TaskStreamMemberPayload(
            supabase_user_id=str(uuid.uuid4()),
            email="multi@example.com",
            full_name="Multi Workspace",
            avatar_url=None,
            role="watcher",
        )
        realm_user_lookup = mock_realm_user_objects.select_related.return_value.filter.return_value
        realm_user_lookup.first.return_value = None
        global_extension_lookup = (
            mock_global_extension_objects.select_related.return_value.filter.return_value
        )
        global_extension_lookup.first.return_value = None
        mock_user_objects.filter.return_value.first.return_value = user

        resolved = _resolve_realm_user(realm, member)

        self.assertEqual(resolved, user)
        mock_global_extension_objects.select_related.return_value.filter.assert_called_once()
        self.assertEqual(
            mock_global_extension_objects.select_related.return_value.filter.call_args.kwargs[
                "zulip_user__realm"
            ],
            realm,
        )
        mock_realm_user_objects.update_or_create.assert_called_once()

    @patch("nodl.api.views.task_streams._get_task_stream")
    @patch("nodl.api.views.task_streams._resolve_members")
    @patch("nodl.api.views.task_streams.bulk_add_subscriptions")
    @patch("nodl.api.views.task_streams.UserProfile.objects")
    @patch("nodl.api.views.task_streams.bulk_remove_subscriptions")
    def test_subscriber_sync_is_idempotent(
        self,
        mock_remove: MagicMock,
        mock_user_objects: MagicMock,
        mock_add: MagicMock,
        mock_resolve_members: MagicMock,
        mock_get_task_stream: MagicMock,
    ) -> None:
        extension = MagicMock()
        extension.zulip_realm = MagicMock(id=1)
        extension.zulip_stream = MagicMock(id=42)
        mock_get_task_stream.return_value = extension
        mock_resolve_members.return_value = []
        mock_user_objects.filter.return_value = []

        payload = {
            "workspace_id": self.workspace_id,
            "task_id": self.task_id,
            "zulip_stream_id": 42,
            "add": [],
            "remove": [],
        }
        request = self.factory.post(
            "/api/v1/internal/task-streams/subscribers",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.is_service_request = True

        response = sync_task_stream_subscribers(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["added"], 0)
        self.assertEqual(data["removed"], 0)
        mock_add.assert_not_called()
        mock_remove.assert_not_called()

    @patch("nodl.api.views.task_streams._get_task_stream")
    @patch("nodl.api.views.task_streams.do_deactivate_stream")
    def test_archive_is_idempotent(
        self,
        mock_deactivate: MagicMock,
        mock_get_task_stream: MagicMock,
    ) -> None:
        extension = MagicMock()
        extension.zulip_stream.deactivated = True
        extension.archived_at = None
        mock_get_task_stream.return_value = extension
        payload = {
            "workspace_id": self.workspace_id,
            "task_id": self.task_id,
            "zulip_stream_id": 42,
        }
        request = self.factory.post(
            "/api/v1/internal/task-streams/archive",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.is_service_request = True

        response = archive_task_stream(request)

        self.assertEqual(response.status_code, 200)
        mock_deactivate.assert_not_called()
        extension.save.assert_called_once_with(update_fields=["archived_at"])
