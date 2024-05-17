from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def render_all_stream_descriptions(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    # FIXME: Application code should not be imported from migrations.
    from zerver.lib.streams import render_stream_description

    Stream = apps.get_model("zerver", "Stream")
    all_streams = Stream.objects.exclude(description="")
    for stream in all_streams:
        stream.rendered_description = render_stream_description(stream.description, stream.realm)
        stream.save(update_fields=["rendered_description"])


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0205_remove_realmauditlog_requires_billing_update"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="rendered_description",
            field=models.TextField(default=""),
        ),
        migrations.RunPython(
            render_all_stream_descriptions, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
