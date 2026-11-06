from django.db import migrations
from django.db.models import F


def make_existing_subscription_colors_default(apps, schema_editor):
    Subscription = apps.get_model("zerver", "Subscription")
    # Migration 0813 copied the previous automatic color into auto_color.
    # Equal values therefore identify subscriptions that have no personal override.
    Subscription.objects.filter(color=F("auto_color")).update(color=None)


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0816_merge_0813_stream_default_color_0815_merge"),
    ]

    operations = [
        migrations.RunPython(
            make_existing_subscription_colors_default,
            migrations.RunPython.noop,
        ),
    ]
