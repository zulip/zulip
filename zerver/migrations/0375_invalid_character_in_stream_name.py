import unicodedata

from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

# There are 66 Unicode non-characters; see
# https://www.unicode.org/faq/private_use.html#nonchar4
unicode_non_chars = set(
    chr(x)
    for x in list(range(0xFDD0, 0xFDF0))  # FDD0 through FDEF, inclusive
    + list(range(0xFFFE, 0x110000, 0x10000))  # 0xFFFE, 0x1FFFE, ... 0x10FFFE inclusive
    + list(range(0xFFFF, 0x110000, 0x10000))  # 0xFFFF, 0x1FFFF, ... 0x10FFFF inclusive
)


def character_is_printable(character: str) -> bool:
    return not (unicodedata.category(character) in ["Cc", "Cs"] or character in unicode_non_chars)


def fix_stream_name(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Stream = apps.get_model("zerver", "Stream")

    streams = Stream.objects.all()
    for stream in streams:
        fixed_stream_name = "".join(
            character for character in stream.name if character_is_printable(character)
        )

        if fixed_stream_name == stream.name:
            continue

        if fixed_stream_name == "":
            stream.name = "Unknown stream {}".format(stream.id)
            stream.save()
            continue

        similar_stream_name_count = Stream.objects.filter(name=fixed_stream_name).count()
        if similar_stream_name_count > 1:
            stream.name = fixed_stream_name + "(#{})".format(stream.id)
            stream.save()


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("zerver", "0374_backfill_user_delete_realmauditlog")]

    operations = [migrations.RunPython(fix_stream_name, reverse_code=migrations.RunPython.noop)]
