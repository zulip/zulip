from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Upper

from zerver.lib.migrate import add_index


class Migration(migrations.Migration):
    atomic = not settings.MIGRATIONS_ADD_REMOVE_INDEXES_CONCURRENTLY
    dependencies = [
        ("zerver", "0111_botuserstatedata"),
    ]

    operations = [
        add_index(
            model_name="mutedtopic",
            index=models.Index(
                "stream", Upper("topic_name"), name="zerver_mutedtopic_stream_topic"
            ),
        ),
    ]
