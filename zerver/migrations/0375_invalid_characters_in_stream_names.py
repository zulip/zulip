import unicodedata

from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

# There are 66 Unicode non-characters; see
# https://www.unicode.org/faq/private_use.html#nonchar4
unicode_non_chars = {
    chr(x)
    for x in list(range(0xFDD0, 0xFDF0))  # FDD0 through FDEF, inclusive
    + list(range(0xFFFE, 0x110000, 0x10000))  # 0xFFFE, 0x1FFFE, ... 0x10FFFE inclusive
    + list(range(0xFFFF, 0x110000, 0x10000))  # 0xFFFF, 0x1FFFF, ... 0x10FFFF inclusive
}


def character_is_printable(character: str) -> bool:
    return not (unicodedata.category(character) in ["Cc", "Cs"] or character in unicode_non_chars)


def fix_stream_names(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Stream = apps.get_model("zerver", "Stream")
    Realm = apps.get_model("zerver", "Realm")

    total_fixed_count = 0
    realm_ids = Realm.objects.values_list("id", flat=True)
    if len(realm_ids) == 0:
        return

    print("")
    for realm_id in realm_ids:
        print(f"Processing realm {realm_id}")
        realm_stream_dicts = Stream.objects.filter(realm_id=realm_id).values("id", "name")
        occupied_stream_names = {stream_dict["name"] for stream_dict in realm_stream_dicts}

        for stream_dict in realm_stream_dicts:
            stream_name = stream_dict["name"]
            fixed_stream_name = "".join(
                [
                    character if character_is_printable(character) else "\N{REPLACEMENT CHARACTER}"
                    for character in stream_name
                ]
            )

            if fixed_stream_name == stream_name:
                continue

            if fixed_stream_name == "":
                fixed_stream_name = "(no name)"

            # The process of stripping invalid characters can lead to collisions,
            # with the new stream name being the same as the name of another existing stream.
            # We append underscore until the name no longer conflicts.
            while fixed_stream_name in occupied_stream_names:
                fixed_stream_name += "_"

            occupied_stream_names.add(fixed_stream_name)
            total_fixed_count += 1
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE zerver_stream SET name = %s WHERE id = %s",
                    [fixed_stream_name, stream_dict["id"]],
                )

    print(f"Fixed {total_fixed_count} stream names")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0374_backfill_user_delete_realmauditlog"),
    ]

    operations = [
        migrations.RunPython(fix_stream_names, reverse_code=migrations.RunPython.noop),
    ]
