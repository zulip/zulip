import unicodedata

from django.db import connection, migrations, models
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


def fix_topics(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Message = apps.get_model("zerver", "Message")
    BATCH_SIZE = 10000
    messages_updated = 0
    lower_bound = 0

    max_id = Message.objects.aggregate(models.Max("id"))["id__max"]
    if max_id is None:
        # Nothing to do if there are no messages.
        return

    print("")
    while lower_bound < max_id:
        print(f"Processed {lower_bound} / {max_id}")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT subject FROM zerver_message WHERE id > %s AND id <= %s",
                [lower_bound, lower_bound + BATCH_SIZE],
            )

            results = cursor.fetchall()

            topics = [r[0] for r in results]
            for topic in topics:
                fixed_topic = "".join(
                    character for character in topic if character_is_printable(character)
                )
                if fixed_topic == topic:
                    continue

                # We don't want empty topics for stream messages, so we
                # use (no topic) if the above clean-up leaves us with an empty string.
                if fixed_topic == "":
                    fixed_topic = "(no topic)"

                cursor.execute(
                    "UPDATE zerver_message SET subject = %s WHERE subject = %s AND id > %s AND id <= %s",
                    [fixed_topic, topic, lower_bound, lower_bound + BATCH_SIZE],
                )
                messages_updated += cursor.rowcount
            lower_bound += BATCH_SIZE

    if messages_updated > 0:
        print(f"Fixed invalid topics for {messages_updated} messages.")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0370_realm_enable_spectator_access"),
    ]

    operations = [
        migrations.RunPython(fix_topics, reverse_code=migrations.RunPython.noop),
    ]
