from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0528_realmauditlog_zerver_realmauditlog_user_activations_idx"),
    ]

    operations = [
        migrations.RunSQL(
            sql="alter table fts_update_log alter column id set data type bigint",
            reverse_sql="alter table fts_update_log alter column id set data type int",
            elidable=True,
        ),
        migrations.RunSQL(
            sql="alter sequence fts_update_log_id_seq as bigint",
            reverse_sql="alter sequence fts_update_log_id_seq as int",
            elidable=True,
        ),
    ]
