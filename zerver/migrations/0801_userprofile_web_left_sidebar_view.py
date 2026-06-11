from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0800_cleanup_case_mismatched_legacy_apns_tokens"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="web_left_sidebar_view",
            field=models.TextField(db_default="channels", default="channels"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="web_left_sidebar_view",
            field=models.TextField(db_default="channels", default="channels"),
        ),
    ]
