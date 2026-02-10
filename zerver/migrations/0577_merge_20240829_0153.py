from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0575_alter_directmessagegroup_group_size"),
        ("zerver", "0576_backfill_imageattachment"),
    ]

    operations = []
