from django.conf import settings
from django.db import migrations, models

from zerver.lib.migrate import remove_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY
    dependencies = [
        ("zilencer", "0037_alter_remoteinstallationcount_unique_together_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="remoteinstallationcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("remote_id__isnull", False)),
                fields=("server", "remote_id"),
                name="unique_remote_installation_count_server_id_remote_id",
            ),
        ),
        remove_index(
            model_name="remoteinstallationcount",
            name="zilencer_remoteinstallat_server_id_remote_id_f72e4c30_idx",
        ),
        migrations.AddConstraint(
            model_name="remoterealmcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("remote_id__isnull", False)),
                fields=("server", "remote_id"),
                name="unique_remote_realm_installation_count_server_id_remote_id",
            ),
        ),
        remove_index(
            model_name="remoterealmcount",
            name="zilencer_remoterealmcount_server_id_remote_id_de1573d8_idx",
        ),
    ]
