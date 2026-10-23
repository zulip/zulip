from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0818_usersetting_web_right_click_opens_message_actions_menu"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="non_workplace_pricing_eligible",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="realm",
            name="has_discount_configured",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
