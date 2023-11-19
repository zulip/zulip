# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from unittest.mock import patch

from django.db.migrations.state import StateApps
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


class UserMessageIndex(MigrationsTestCase):
    migrate_from = "0485_alter_usermessage_flags_and_add_index"
    migrate_to = "0486_clear_old_data_for_unused_usermessage_flags"

    @override
    def setUp(self) -> None:
        with patch("builtins.print") as _:
            super().setUp()

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        UserMessage = apps.get_model("zerver", "usermessage")

        um_1 = UserMessage.objects.get(id=1)
        um_1.flags.topic_wildcard_mentioned = True
        um_1.flags.stream_wildcard_mentioned = True
        um_1.flags.force_expand = True
        um_1.save()

        um_2 = UserMessage.objects.get(id=2)
        um_2.flags.group_mentioned = True
        um_2.flags.topic_wildcard_mentioned = True
        um_2.flags.mentioned = True
        um_2.flags.force_collapse = True
        um_2.save()

        um_1 = UserMessage.objects.get(id=1)
        um_2 = UserMessage.objects.get(id=2)

        self.assertTrue(um_1.flags.topic_wildcard_mentioned)
        self.assertTrue(um_1.flags.stream_wildcard_mentioned)
        self.assertTrue(um_1.flags.force_expand)
        self.assertTrue(um_2.flags.group_mentioned)
        self.assertTrue(um_2.flags.topic_wildcard_mentioned)
        self.assertTrue(um_2.flags.mentioned)
        self.assertTrue(um_2.flags.force_collapse)

    def test_clear_topic_wildcard_and_group_mentioned_flags(self) -> None:
        UserMessage = self.apps.get_model("zerver", "usermessage")

        um_1 = UserMessage.objects.get(id=1)
        um_2 = UserMessage.objects.get(id=2)

        self.assertFalse(um_1.flags.topic_wildcard_mentioned)
        self.assertTrue(um_1.flags.stream_wildcard_mentioned)
        self.assertFalse(um_1.flags.force_expand)
        self.assertFalse(um_2.flags.group_mentioned)
        self.assertFalse(um_2.flags.topic_wildcard_mentioned)
        self.assertTrue(um_2.flags.mentioned)
        self.assertFalse(um_2.flags.force_collapse)
