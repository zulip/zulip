from datetime import timedelta

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.create_realm import do_create_realm
from zerver.actions.realm_settings import do_set_realm_property
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Realm
from zerver.models.realms import get_realm


class CommunitiesApiViewTest(ZulipTestCase):
    """Tests for GET /json/communities — the communities directory listing endpoint."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.url = "/json/communities"

    def test_returns_empty_list_when_no_eligible_realms(self) -> None:
        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        self.assertEqual(data["realms"], [])
        self.assertIn("org_types", data)

    def test_returns_eligible_realm(self) -> None:
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.invite_required = False
        realm.emails_restricted_to_domains = False
        realm.save()
        do_set_realm_property(realm, "description", "A great community", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_ids = [r["id"] for r in data["realms"]]
        self.assertIn(realm.id, realm_ids)

    def test_excludes_realm_with_empty_description(self) -> None:
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.invite_required = False
        realm.emails_restricted_to_domains = False
        realm.save()
        # Ensure description is empty (the default sentinel value).
        do_set_realm_property(realm, "description", "", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_ids = [r["id"] for r in data["realms"]]
        self.assertNotIn(realm.id, realm_ids)

    def test_excludes_realm_not_wanting_to_advertise(self) -> None:
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = False
        realm.invite_required = False
        realm.emails_restricted_to_domains = False
        realm.save()
        do_set_realm_property(realm, "description", "A great community", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_ids = [r["id"] for r in data["realms"]]
        self.assertNotIn(realm.id, realm_ids)

    def test_excludes_demo_organization(self) -> None:
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.invite_required = False
        realm.emails_restricted_to_domains = False
        realm.demo_organization_scheduled_deletion_date = timezone_now() + timedelta(days=15)
        realm.save()
        do_set_realm_property(realm, "description", "A great community", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_ids = [r["id"] for r in data["realms"]]
        self.assertNotIn(realm.id, realm_ids)

    def test_excludes_private_realm(self) -> None:
        """A realm that requires invite and has no web-public streams should not appear."""
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.invite_required = True
        realm.emails_restricted_to_domains = True
        realm.enable_spectator_access = False
        realm.save(
            update_fields=[
                "want_advertise_in_communities_directory",
                "invite_required",
                "emails_restricted_to_domains",
                "enable_spectator_access",
            ]
        )
        do_set_realm_property(realm, "description", "A private community", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_ids = [r["id"] for r in data["realms"]]
        self.assertNotIn(realm.id, realm_ids)

    def test_realm_dict_has_expected_fields(self) -> None:
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.invite_required = False
        realm.emails_restricted_to_domains = False
        realm.org_type = Realm.ORG_TYPES["community"]["id"]
        realm.save()
        do_set_realm_property(realm, "description", "A great community", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_entry = next(r for r in data["realms"] if r["id"] == realm.id)

        self.assertIn("id", realm_entry)
        self.assertIn("name", realm_entry)
        self.assertIn("description", realm_entry)
        self.assertIn("icon_url", realm_entry)
        self.assertIn("realm_url", realm_entry)
        self.assertIn("date_created", realm_entry)
        self.assertIn("org_type_key", realm_entry)

    def test_org_types_only_includes_categories_with_eligible_realms(self) -> None:
        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.invite_required = False
        realm.emails_restricted_to_domains = False
        realm.org_type = Realm.ORG_TYPES["opensource"]["id"]
        realm.save()
        do_set_realm_property(realm, "description", "An open source project", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()

        self.assertIn("opensource", data["org_types"])
        # research has no eligible realms so it should not appear.
        self.assertNotIn("research", data["org_types"])

    def test_accessible_without_authentication(self) -> None:
        """The endpoint must be accessible anonymously (needed for desktop/mobile clients)."""
        result = self.client_get(self.url)
        self.assert_json_success(result)

    def test_multiple_eligible_realms(self) -> None:
        realm1 = do_create_realm(
            string_id="community_one",
            name="Community One",
            invite_required=False,
            enable_read_receipts=False,
        )
        realm1.want_advertise_in_communities_directory = True
        realm1.emails_restricted_to_domains = False
        realm1.org_type = Realm.ORG_TYPES["community"]["id"]
        realm1.save()
        do_set_realm_property(realm1, "description", "First community", acting_user=None)

        realm2 = do_create_realm(
            string_id="community_two",
            name="Community Two",
            invite_required=False,
            enable_read_receipts=False,
        )
        realm2.want_advertise_in_communities_directory = True
        realm2.emails_restricted_to_domains = False
        realm2.org_type = Realm.ORG_TYPES["research"]["id"]
        realm2.save()
        do_set_realm_property(realm2, "description", "Second community", acting_user=None)

        result = self.client_get(self.url)
        self.assert_json_success(result)
        data = result.json()
        realm_ids = [r["id"] for r in data["realms"]]
        self.assertIn(realm1.id, realm_ids)
        self.assertIn(realm2.id, realm_ids)

        # Both org types should appear.
        self.assertIn("community", data["org_types"])
        self.assertIn("research", data["org_types"])
