from typing import Any
from uuid import uuid4

import responses
from django.utils.timezone import now as timezone_now
from requests.exceptions import ConnectionError
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zilencer.lib.communities_directory import (
    get_remote_realms_asking_to_be_advertised,
    probe_remote_realms_for_communities_directory,
)
from zilencer.models import RemoteRealm, RemoteZulipServer


class ProbeRemoteRealmsForCommunitiesDirectoryTest(ZulipTestCase):
    SERVER_SETTINGS_URL = "https://community.example.com/api/v1/server_settings"
    LOGGER_NAME = "zilencer.lib.communities_directory"

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
        )

    def probe_records_reachability(self, **response_kwargs: Any) -> bool:
        responses.reset()
        responses.add(responses.GET, self.SERVER_SETTINGS_URL, **response_kwargs)

        probe_remote_realms_for_communities_directory()

        self.remote_realm.refresh_from_db()
        reached = self.remote_realm.last_reachable_datetime is not None
        self.remote_realm.last_reachable_datetime = None
        self.remote_realm.save(update_fields=["last_reachable_datetime"])
        return reached

    @responses.activate
    def test_only_a_live_zulip_server_counts_as_reachable(self) -> None:
        with self.assertLogs(self.LOGGER_NAME, level="INFO"):
            self.assertTrue(
                self.probe_records_reachability(json={"zulip_version": "11.0"}, status=200)
            )

            self.assertFalse(self.probe_records_reachability(status=500))
            self.assertFalse(self.probe_records_reachability(body="not json", status=200))
            # Something answered, but it is not a Zulip server.
            self.assertFalse(self.probe_records_reachability(json={}, status=200))
            self.assertFalse(self.probe_records_reachability(body=ConnectionError("unreachable")))

    @responses.activate
    def test_organizations_we_would_not_advertise_are_not_probed(self) -> None:
        self.remote_realm.description = ""
        self.remote_realm.save(update_fields=["description"])

        with self.assertLogs(self.LOGGER_NAME, level="INFO"):
            probe_remote_realms_for_communities_directory()

        self.assert_length(responses.calls, 0)
        self.remote_realm.refresh_from_db()
        self.assertIsNone(self.remote_realm.last_reachable_datetime)

    def test_organizations_that_are_gone_are_not_offered(self) -> None:
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
