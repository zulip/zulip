import pathlib
from typing import Any
from uuid import uuid4

import pyvips
import responses
from django.conf import settings
from django.utils.timezone import now as timezone_now
from requests.exceptions import ConnectionError
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import read_test_image_file
from zerver.lib.thumbnail import DEFAULT_AVATAR_SIZE
from zerver.lib.upload import get_upload_backend
from zilencer.lib.communities_directory import (
    get_remote_realms_asking_to_be_advertised,
    probe_remote_realms_for_communities_directory,
)
from zilencer.models import RemoteRealm, RemoteZulipServer

logger_string = "zilencer.lib.communities_directory"


class ProbeRemoteRealmsForCommunitiesDirectoryTest(ZulipTestCase):
    SERVER_SETTINGS_URL = "https://community.example.com/api/v1/server_settings"
    ICON_URL = "https://community.example.com/user_avatars/2/realm/icon.png?version=3"
    NEW_ICON_URL = "https://community.example.com/user_avatars/2/realm/icon.png?version=4"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.server = RemoteZulipServer.objects.create(
            uuid=uuid4(),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=timezone_now(),
        )
        self.remote_realm = RemoteRealm.objects.create(
            server=self.server,
            uuid=uuid4(),
            uuid_owner_secret="dummy-secret",
            host="community.example.com",
            realm_date_created=timezone_now(),
            asks_to_advertise_in_communities_directory=True,
            description="A place to talk about Zulip",
            invite_required=False,
            icon_url=self.ICON_URL,
            # An organization whose icon we have already copied.
            last_mirrored_icon_url=self.ICON_URL,
            mirrored_icon_version=1,
        )

    def recorded_as_reachable(self, **response_kwargs: Any) -> bool:
        responses.reset()
        responses.add(responses.GET, self.SERVER_SETTINGS_URL, **response_kwargs)

        probe_remote_realms_for_communities_directory()
        self.remote_realm.refresh_from_db()
        reached = self.remote_realm.last_reachable_datetime is not None

        # reset
        self.remote_realm.last_reachable_datetime = None
        self.remote_realm.save(update_fields=["last_reachable_datetime"])

        return reached

    @responses.activate
    def test_remote_realm_reachability(self) -> None:
        with self.assertLogs(logger_string, level="INFO") as m:
            self.assertTrue(self.recorded_as_reachable(json={"zulip_version": "11.0"}, status=200))

            self.assertFalse(self.recorded_as_reachable(status=500))
            self.assertFalse(self.recorded_as_reachable(body="not json", status=200))
            # Something answered, but it is not a Zulip server.
            self.assertFalse(self.recorded_as_reachable(json={}, status=200))
            # Valid JSON that is not an object at all.
            self.assertFalse(self.recorded_as_reachable(body="null", status=200))
            self.assertFalse(self.recorded_as_reachable(body=ConnectionError("unreachable")))

        host = self.remote_realm.host
        self.assertEqual(
            m.output,
            [
                f"INFO:{logger_string}:Probed 1 organizations, reached 1",
                f"INFO:{logger_string}:Probe for {host} returned status 500",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} did not return valid JSON",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} did not answer as a Zulip realm",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} did not answer as a Zulip realm",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} failed: unreachable",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
            ],
        )

    @responses.activate
    def test_invalid_host(self) -> None:
        # The host is whatever the organization's server uploaded.
        self.remote_realm.host = "["
        self.remote_realm.save(update_fields=["host"])

        with self.assertLogs(logger_string, level="INFO") as m:
            probe_remote_realms_for_communities_directory()

        self.assertEqual(
            m.output,
            [
                f"INFO:{logger_string}:Probe for [ failed: Invalid IPv6 URL",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
            ],
        )
        self.assert_length(responses.calls, 0)
        self.remote_realm.refresh_from_db()
        self.assertIsNone(self.remote_realm.last_reachable_datetime)

    @responses.activate
    def test_organization_not_meeting_base_criteria_is_not_probed(self) -> None:
        self.remote_realm.description = ""
        self.remote_realm.save(update_fields=["description"])

        with self.assertLogs(logger_string, level="INFO") as m:
            probe_remote_realms_for_communities_directory()

        self.assertEqual(m.output, [f"INFO:{logger_string}:Probed 0 organizations, reached 0"])
        self.assert_length(responses.calls, 0)
        self.remote_realm.refresh_from_db()
        self.assertIsNone(self.remote_realm.last_reachable_datetime)

    @responses.activate
    def test_icon_is_mirrored_when_it_changes(self) -> None:
        responses.add(
            responses.GET, self.SERVER_SETTINGS_URL, json={"zulip_version": "11.0"}, status=200
        )
        responses.add(
            responses.GET, self.NEW_ICON_URL, body=read_test_image_file("img.jpg"), status=200
        )
        self.remote_realm.icon_url = self.NEW_ICON_URL
        self.remote_realm.save(update_fields=["icon_url"])

        self.assertEqual(self.remote_realm.last_mirrored_icon_url, self.ICON_URL)
        self.assertEqual(self.remote_realm.mirrored_icon_version, 1)

        with self.assertLogs(logger_string, level="INFO"):
            probe_remote_realms_for_communities_directory()

        self.remote_realm.refresh_from_db()
        self.assertEqual(self.remote_realm.last_mirrored_icon_url, self.NEW_ICON_URL)
        self.assertEqual(self.remote_realm.mirrored_icon_version, 2)

        # What we serve is our own re-encoded copy, at a URL that changes
        # with the version.
        backend = get_upload_backend()
        self.assertEqual(
            backend.get_remote_realm_icon_url(str(self.remote_realm.uuid), 2),
            f"/user_avatars/remote_realms/{self.remote_realm.uuid}/icon.png?version=2",
        )
        assert settings.LOCAL_AVATARS_DIR is not None
        stored = (
            pathlib.Path(settings.LOCAL_AVATARS_DIR)
            / "remote_realms"
            / str(self.remote_realm.uuid)
            / "icon.png"
        )
        self.assertTrue(stored.exists())
        # A JPG went in; what we serve is our own re-encoded PNG.
        stored_data = stored.read_bytes()
        self.assertTrue(stored_data.startswith(b"\x89PNG"))
        stored_image = pyvips.Image.new_from_buffer(stored_data, "")
        self.assertEqual(DEFAULT_AVATAR_SIZE, stored_image.height)
        self.assertEqual(DEFAULT_AVATAR_SIZE, stored_image.width)

        # The copy is not fetched again while the organization's icon is
        # unchanged, so a pass costs one request.
        responses.calls.reset()
        with self.assertLogs(logger_string, level="INFO"):
            probe_remote_realms_for_communities_directory()

        self.assert_length(responses.calls, 1)
        self.remote_realm.refresh_from_db()
        self.assertEqual(self.remote_realm.mirrored_icon_version, 2)

    @responses.activate
    def test_icon_we_cannot_use_leaves_the_copy_we_have(self) -> None:
        responses.add(
            responses.GET, self.SERVER_SETTINGS_URL, json={"zulip_version": "11.0"}, status=200
        )
        responses.add(responses.GET, self.NEW_ICON_URL, body=b"not an image", status=200)
        self.remote_realm.icon_url = self.NEW_ICON_URL
        self.remote_realm.save(update_fields=["icon_url"])

        with self.assertLogs(logger_string, level="INFO"):
            probe_remote_realms_for_communities_directory()

        self.remote_realm.refresh_from_db()
        # The organization stays reachable, and keeps the copy we already have.
        self.assertIsNotNone(self.remote_realm.last_reachable_datetime)
        self.assertEqual(self.remote_realm.last_mirrored_icon_url, self.ICON_URL)
        self.assertEqual(self.remote_realm.mirrored_icon_version, 1)

    def mirror_succeeds(self, **response_kwargs: Any) -> bool:
        responses.reset()
        responses.add(
            responses.GET, self.SERVER_SETTINGS_URL, json={"zulip_version": "11.0"}, status=200
        )
        responses.add(responses.GET, self.NEW_ICON_URL, **response_kwargs)
        # Start each case from an organization whose icon has just changed.
        self.remote_realm.icon_url = self.NEW_ICON_URL
        self.remote_realm.last_mirrored_icon_url = self.ICON_URL
        self.remote_realm.save(update_fields=["icon_url", "last_mirrored_icon_url"])

        probe_remote_realms_for_communities_directory()

        self.remote_realm.refresh_from_db()
        return self.remote_realm.last_mirrored_icon_url == self.NEW_ICON_URL

    @responses.activate
    def test_only_an_image_we_can_re_encode_is_mirrored(self) -> None:
        with self.assertLogs(logger_string, level="INFO"):
            self.assertTrue(self.mirror_succeeds(body=read_test_image_file("img.png"), status=200))

            self.assertFalse(self.mirror_succeeds(status=404))
            self.assertFalse(self.mirror_succeeds(body=b"not an image", status=200))
            self.assertFalse(self.mirror_succeeds(body=ConnectionError("unreachable")))

            # An icon larger than we accept.
            with self.settings(MAX_ICON_FILE_SIZE_MIB=0):
                self.assertFalse(
                    self.mirror_succeeds(body=read_test_image_file("img.png"), status=200)
                )

    def test_get_remote_realms_asking_to_be_advertised(self) -> None:
        self.assertEqual(list(get_remote_realms_asking_to_be_advertised()), [self.remote_realm])

        for attr_name in ["registration_deactivated", "realm_deactivated", "realm_locally_deleted"]:
            setattr(self.remote_realm, attr_name, True)
            self.remote_realm.save(update_fields=[attr_name])
            self.assertEqual(list(get_remote_realms_asking_to_be_advertised()), [])
            setattr(self.remote_realm, attr_name, False)
            self.remote_realm.save(update_fields=[attr_name])

        self.remote_realm.asks_to_advertise_in_communities_directory = False
        self.remote_realm.save(update_fields=["asks_to_advertise_in_communities_directory"])
        self.assertEqual(list(get_remote_realms_asking_to_be_advertised()), [])
