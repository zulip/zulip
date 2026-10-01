from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0817_subscription_web_left_sidebar_topics_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="web_right_click_opens_message_actions_menu",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="web_right_click_opens_message_actions_menu",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
