from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F, Func, Q, TextField, Value
from django.db.models.functions import Coalesce, NullIf

# Copied from zerver.lib.upload.remove_control_characters, less the
# NUL byte: PostgreSQL cannot store NUL in a text column, so it can
# never be present here, and it cannot be sent as a query parameter
# either.
CONTROL_CHARACTERS = r"[\x01-\x1f\x7f]"

# The names clean_uploaded_file_name replaces, because they leave
# nothing for "Save as..." to use.
PLACEHOLDER_FILE_NAMES = ["", ".", ".."]


def strip_control_characters(field_name: str) -> Func:
    return Func(
        F(field_name),
        Value(CONTROL_CHARACTERS),
        Value(""),
        Value("g"),
        function="regexp_replace",
    )


def stripped_file_name() -> Func:
    file_name = strip_control_characters("file_name")
    for placeholder in PLACEHOLDER_FILE_NAMES:
        file_name = NullIf(file_name, Value(placeholder))
    return Coalesce(file_name, Value("uploaded-file"), output_field=TextField())


def stripped_content_type() -> Func:
    # NULL is the "we don't know" value that both serving paths
    # already handle by guessing from the file name.
    return NullIf(strip_control_characters("content_type"), Value(""), output_field=TextField())


def strip_control_characters_from_attachments(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    for model_name in ("Attachment", "ArchivedAttachment"):
        model = apps.get_model("zerver", model_name)
        count = model.objects.filter(
            Q(file_name__regex=CONTROL_CHARACTERS) | Q(content_type__regex=CONTROL_CHARACTERS)
        ).update(
            file_name=stripped_file_name(),
            content_type=stripped_content_type(),
        )
        if count > 0:
            print(f"\nStripped control characters from {count} {model_name} rows.")


class Migration(migrations.Migration):
    """Uploads stored the client's filename and content type nearly
    verbatim, so a control character in either could reach the
    database; we now strip them on the way in, but existing rows keep
    what was stored.

    A CR or LF is the harmful case: serve_local rebuilds
    Content-Disposition and Content-Type from these columns on every
    read, and Django raises BadHeaderError on either, leaving the
    attachment undownloadable until the row is repaired. The rest
    serve correctly, and are cleaned up here only for tidiness.
    """

    # Each .update() is a single statement, so committing them
    # separately avoids holding a transaction open across the scans.
    atomic = False

    dependencies = [
        ("zerver", "0806_stream_default_push_notifications"),
    ]

    operations = [
        migrations.RunPython(
            strip_control_characters_from_attachments,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
