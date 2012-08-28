from django.db import migrations


class Migration(migrations.Migration):
    """
    Finalizes the migration to the new UserPresence model.
    We can get rid of the old table together with its data.
    """

    dependencies = [
        ("zerver", "0444_userpresence_fill_data"),
    ]

    operations = [migrations.DeleteModel(name="UserPresenceOld")]
