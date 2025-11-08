from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0294_remove_userprofile_pointer"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.UniqueConstraint(
                models.F("realm"),
                Upper(models.F("email")),
                name="zerver_userprofile_realm_id_email_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.UniqueConstraint(
                models.F("realm"),
                Upper(models.F("delivery_email")),
                name="zerver_userprofile_realm_id_delivery_email_uniq",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="userprofile",
            unique_together=set(),
        ),
    ]
