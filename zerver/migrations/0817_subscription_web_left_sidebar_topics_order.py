from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0816_usersetting_web_left_sidebar_topics_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="web_left_sidebar_topics_order",
            field=models.PositiveSmallIntegerField(db_default=0, default=0),
        ),
    ]
