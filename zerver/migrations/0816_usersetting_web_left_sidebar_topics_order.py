from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0815_merge"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="web_left_sidebar_topics_order",
            field=models.PositiveSmallIntegerField(db_default=1, default=1),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="web_left_sidebar_topics_order",
            field=models.PositiveSmallIntegerField(db_default=1, default=1),
        ),
    ]
