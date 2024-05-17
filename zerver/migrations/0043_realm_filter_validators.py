from typing import List

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0042_attachment_file_name_length"),
    ]

    operations: List[migrations.operations.base.Operation] = []
