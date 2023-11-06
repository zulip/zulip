# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from typing import Optional

from django.db.migrations.state import StateApps
from django.utils.timezone import now
from typing_extensions import override

from zerver.lib.test_classes import MigrationsTestCase

# Important note: These tests are very expensive, and details of
# Django's database transaction model mean it does not super work to
# have a lot of migrations tested in this file at once; so we usually
# delete the old migration tests when adding a new one, so this file
# always has a single migration test in it as an example.
#
# The error you get with multiple similar tests doing migrations on
# the same table is this (table name may vary):
#
#   django.db.utils.OperationalError: cannot ALTER TABLE
#   "zerver_subscription" because it has pending trigger events


class PushBouncerBackfillIosAppId(MigrationsTestCase):
    @property
    @override
    def app(self) -> str:
        return "zilencer"

    migrate_from = "0031_alter_remoteinstallationcount_remote_id_and_more"
    migrate_to = "0032_remotepushdevicetoken_backfill_ios_app_id"

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        user = self.example_user("hamlet")

        RemoteZulipServer = apps.get_model("zilencer", "RemoteZulipServer")
        server = RemoteZulipServer.objects.create(
            uuid="6cde5f7a-1f7e-4978-9716-49f69ebfc9fe",
            api_key="secret",
            hostname="chat.example",
            last_updated=now(),
        )

        RemotePushDeviceToken = apps.get_model("zilencer", "RemotePushDeviceToken")

        def create(kind: int, token: str, ios_app_id: Optional[str]) -> None:
            RemotePushDeviceToken.objects.create(
                server=server,
                user_uuid=user.uuid,
                kind=kind,
                token=token,
                ios_app_id=ios_app_id,
            )

        kinds = {choice[1]: choice[0] for choice in RemotePushDeviceToken.kind.field.choices}
        create(kinds["apns"], "1234", None)
        create(kinds["apns"], "2345", "example.app")
        create(kinds["gcm"], "3456", None)

    @override
    def tearDown(self) -> None:
        RemotePushDeviceToken = self.apps.get_model("zilencer", "RemotePushDeviceToken")
        RemotePushDeviceToken.objects.all().delete()

    def test_worked(self) -> None:
        RemotePushDeviceToken = self.apps.get_model("zilencer", "RemotePushDeviceToken")
        self.assertEqual(
            dict(RemotePushDeviceToken.objects.values_list("token", "ios_app_id")),
            {"1234": "org.zulip.Zulip", "2345": "example.app", "3456": None},
        )
