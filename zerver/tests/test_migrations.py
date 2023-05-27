# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.

from django.db.migrations.state import StateApps

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models

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
#
# As a result, we generally mark these tests as skipped once they have
# been tested for a migration being merged.


class RealmPlaygroundURLPrefix(MigrationsTestCase):
    migrate_from = "0462_realmplayground_url_template"
    migrate_to = "0463_backfill_realmplayground_url_template"

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        iago = self.example_user("iago")
        RealmPlayground = apps.get_model("zerver", "RealmPlayground")

        urls = [
            "http://example.com/",
            "https://example.com/{",
            "https://example.com/{}",
            "https://example.com/{val}",
            "https://example.com/{code}",
        ]
        self.realm_playground_ids = []

        for index, url in enumerate(urls):
            self.realm_playground_ids.append(
                RealmPlayground.objects.create(
                    realm=iago.realm,
                    name=f"Playground {index}",
                    pygments_language="Python",
                    url_prefix=url,
                    url_template=None,
                ).id
            )
        self.realm_playground_ids.append(
            RealmPlayground.objects.create(
                realm=iago.realm,
                name="Existing Playground",
                pygments_language="Python",
                url_prefix="https://example.com",
                url_template="https://example.com/{code}",
            ).id
        )

    def test_converted_url_templates(self) -> None:
        RealmPlayground = self.apps.get_model("zerver", "RealmPlayground")

        expected_urls = [
            "http://example.com/{code}",
            "https://example.com/%7B{code}",
            "https://example.com/%7B%7D{code}",
            "https://example.com/%7Bval%7D{code}",
            "https://example.com/%7Bcode%7D{code}",
            "https://example.com/{code}",
        ]

        for realm_playground_id, expected_url in zip(self.realm_playground_ids, expected_urls):
            realm_playground = RealmPlayground.objects.get(id=realm_playground_id)
            self.assertEqual(realm_playground.url_template, expected_url)
