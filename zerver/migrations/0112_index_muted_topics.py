from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0111_botuserstatedata"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="mutedtopic",
            index=models.Index(
                "stream", Upper("topic_name"), name="zerver_mutedtopic_stream_topic"
            ),
        ),
    ]
