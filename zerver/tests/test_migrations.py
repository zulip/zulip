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


class LinkifierURLFormatString(MigrationsTestCase):
    migrate_from = "0440_realmfilter_url_template"
    migrate_to = "0441_backfill_realmfilter_url_template"

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        RealmFilter = apps.get_model("zerver", "RealmFilter")

        iago = self.example_user("iago")

        urls = [
            "http://example.com/",
            "https://example.com/",
            "https://user:password@example.com/",
            "https://example.com/@user/thing",
            "https://example.com/!path",
            "https://example.com/foo.bar",
            "https://example.com/foo[bar]",
            "https://example.com/{foo}",
            "https://example.com/{foo}{bars}",
            "https://example.com/{foo}/and/{bar}",
            "https://example.com/?foo={foo}",
            "https://example.com/%ab",
            "https://example.com/%ba",
            "https://example.com/%21",
            "https://example.com/words%20with%20spaces",
            "https://example.com/back%20to%20{back}",
            "https://example.com/encoded%2fwith%2fletters",
            "https://example.com/encoded%2Fwith%2Fupper%2Fcase%2Fletters",
            "https://example.com/%%",
            "https://example.com/%%(",
            "https://example.com/%%()",
            "https://example.com/%%(foo",
            "https://example.com/%%(foo)",
            "https://example.com/%%(foo)s",
            "https://example.com/%(foo)s",
            "https://example.com/%(foo)s%(bar)s",
        ]
        self.linkifier_ids = []

        for index, url in enumerate(urls):
            self.linkifier_ids.append(
                RealmFilter.objects.create(
                    realm=iago.realm,
                    pattern=f"dummy{index}",
                    url_format_string=url,
                ).id
            )

    def test_converted_url_templates(self) -> None:
        RealmFilter = self.apps.get_model("zerver", "RealmFilter")

        expected_urls = [
            "http://example.com/",
            "https://example.com/",
            "https://user:password@example.com/",
            "https://example.com/@user/thing",
            "https://example.com/!path",
            "https://example.com/foo.bar",
            "https://example.com/foo[bar]",
            "https://example.com/%7Bfoo%7D",
            "https://example.com/%7Bfoo%7D%7Bbars%7D",
            "https://example.com/%7Bfoo%7D/and/%7Bbar%7D",
            "https://example.com/?foo=%7Bfoo%7D",
            "https://example.com/%ab",
            "https://example.com/%ba",
            "https://example.com/%21",
            "https://example.com/words%20with%20spaces",
            "https://example.com/back%20to%20%7Bback%7D",
            "https://example.com/encoded%2fwith%2fletters",
            "https://example.com/encoded%2Fwith%2Fupper%2Fcase%2Fletters",
            "https://example.com/%",
            "https://example.com/%(",
            "https://example.com/%()",
            "https://example.com/%(foo",
            "https://example.com/%(foo)",
            "https://example.com/%(foo)s",
            "https://example.com/{foo}",
            "https://example.com/{foo}{bar}",
        ]

        for linkifier_id, expected in zip(self.linkifier_ids, expected_urls):
            linkifier = RealmFilter.objects.filter(id=linkifier_id).first()
            self.assertIsNotNone(linkifier)
            self.assertEqual(linkifier.url_template, expected)
