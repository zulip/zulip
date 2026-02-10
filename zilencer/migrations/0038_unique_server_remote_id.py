from django.db import migrations, models


class Migration(migrations.Migration):
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
        migrations.RemoveIndex(
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
        migrations.RemoveIndex(
            model_name="remoterealmcount",
            name="zilencer_remoterealmcount_server_id_remote_id_de1573d8_idx",
        ),
    ]
