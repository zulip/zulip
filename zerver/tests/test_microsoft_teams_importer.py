import os

from zerver.data_import.microsoft_teams import do_convert_directory
from zerver.lib.import_realm import do_import_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm
from zerver.models.users import UserProfile, get_user_by_delivery_email
from zerver.tests.test_import_export import make_export_output_dir


class MicrosoftTeamsImporterTest(ZulipTestCase):
    example_microsoft_teams_user_map = dict(
        hamlet="hamlet@lemonstand.onmicrosoft.com",
        othello="othello@lemonstand.onmicrosoft.com",
        cordelia="cordelia@lemonstand.onmicrosoft.com",
        pieter="pieterkwok@lemonstand.onmicrosoft.com",
    )

    def setUp(self) -> None:
        self.converted_file_output_dir = make_export_output_dir()
        self.test_realm_subdomain = "test-import-teams-realm"
        return super().setUp()

    def convert_microsoft_teams_export_fixture(self, fixture_folder: str) -> None:
        fixture_file_path = self.fixture_file_name(fixture_folder, "microsoft_teams_fixtures")
        if not os.path.isdir(fixture_file_path):
            raise AssertionError(f"Fixture file not found: {fixture_file_path}")
        with self.assertLogs(level="INFO"), self.settings(EXTERNAL_HOST="zulip.example.com"):
            do_convert_directory(fixture_file_path, self.converted_file_output_dir)

    def import_microsoft_teams_export_fixture(self, fixture_folder: str) -> None:
        self.convert_microsoft_teams_export_fixture(fixture_folder)
        with self.settings(BILLING_ENABLED=False), self.assertLogs(level="INFO"):
            do_import_realm(self.converted_file_output_dir, self.test_realm_subdomain)

    def get_imported_microsoft_teams_user(
        self, name: str, imported_realm: str = "test-import-teams-realm"
    ) -> UserProfile:
        email = self.example_microsoft_teams_user_map[name]
        return get_user_by_delivery_email(email, get_realm(imported_realm))

    def test_import_users(self) -> None:
        self.convert_microsoft_teams_export_fixture("TeamsDataExport/")
        print(UserProfile.objects.filter(realm=get_realm(self.test_realm_subdomain)))
        for name in self.example_microsoft_teams_user_map:
            imported_user = self.get_imported_microsoft_teams_user(name)
            print(imported_user)
