# Generated migration for adding use_in_mention_suggestions field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0001_squashed_0999_final'),  # Update with actual latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='customprofilefield',
            name='use_in_mention_suggestions',
            field=models.BooleanField(default=False, db_default=False),
        ),
    ]
