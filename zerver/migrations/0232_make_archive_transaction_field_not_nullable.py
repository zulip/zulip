import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Tables cannot have data deleted from them and be altered in a single transaction,
    but we need the DELETEs to be atomic together. So we set atomic=False for the migration
    in general, and run the DELETEs in one transaction, and AlterField in another.
    """

    atomic = False

    dependencies = [
        ("zerver", "0231_add_archive_transaction_model"),
    ]

    operations = [
        migrations.RunSQL(
            """
        BEGIN;
        DELETE FROM zerver_archivedusermessage;
        DELETE FROM zerver_archivedreaction;
        DELETE FROM zerver_archivedsubmessage;
        DELETE FROM zerver_archivedattachment_messages;
        DELETE FROM zerver_archivedattachment;
        DELETE FROM zerver_archivedmessage;
        DELETE FROM zerver_archivetransaction;
        COMMIT;
        """,
            elidable=True,
        ),
        migrations.AlterField(
            model_name="archivedmessage",
            name="archive_transaction",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="zerver.ArchiveTransaction"
            ),
        ),
    ]
