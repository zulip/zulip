from typing import Any, List

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0126_prereg_remove_users_without_realm"),
    ]

    operations: List[Any] = [
        # There was a migration here, which wasn't ready for wide deployment
        # and was backed out.  This placeholder is left behind to avoid
        # confusing the migration engine on any installs that applied the
        # migration.  (Fortunately no reverse migration is needed.)
    ]
