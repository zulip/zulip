import time
from typing import Any, List, Optional, Type, TypedDict

import orjson
from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Min

BATCH_SIZE = 10000
STREAM = 2


# Legacy TypedDict has "prev_topic" field for any edit_history entries that
# were saved to the database after the legacy "prev_subject" field stopped
# being written to the database in the pre-migration commit.
class LegacyEditHistoryEvent(TypedDict, total=False):
    user_id: int
    timestamp: int
    prev_stream: int
    prev_subject: str
    prev_topic: str
    prev_content: str
    prev_rendered_content: Optional[str]
    prev_rendered_content_version: Optional[int]


class EditHistoryEvent(TypedDict, total=False):
    user_id: Optional[int]
    timestamp: int
    prev_stream: int
    stream: int
    prev_topic: str
    topic: str
    prev_content: str
    prev_rendered_content: Optional[str]
    prev_rendered_content_version: Optional[int]


@transaction.atomic
def backfill_message_edit_history_chunk(
    first_id: int, last_id: int, message_model: Type[Any]
) -> None:
    """
    Migrate edit history events for the messages in the provided range to:
    * Rename prev_subject => prev_topic.
    * Provide topic and stream fields with the current values.

    The range of message IDs to be processed is inclusive on both ends.
    """
    messages = (
        message_model.objects.select_for_update()
        .only(
            "recipient",
            "recipient__type",
            "recipient__type_id",
            "subject",
            "edit_history",
        )
        .filter(edit_history__isnull=False, id__range=(first_id, last_id))
    )

    for message in messages:
        legacy_edit_history: List[LegacyEditHistoryEvent] = orjson.loads(message.edit_history)
        message_type = message.recipient.type
        modern_edit_history: List[EditHistoryEvent] = []

        # Only Stream messages have topic / stream edit history data.
        if message_type == STREAM:
            topic = message.subject
            stream_id = message.recipient.type_id

        for edit_history_event in legacy_edit_history:
            modern_entry: EditHistoryEvent = {
                "user_id": edit_history_event.get("user_id"),
                "timestamp": edit_history_event["timestamp"],
            }

            if "prev_content" in edit_history_event:
                modern_entry["prev_content"] = edit_history_event["prev_content"]
                modern_entry["prev_rendered_content"] = edit_history_event["prev_rendered_content"]
                modern_entry["prev_rendered_content_version"] = edit_history_event[
                    "prev_rendered_content_version"
                ]

            if message_type == STREAM:
                if "prev_subject" in edit_history_event:
                    # Add topic edit key/value pairs from legacy format.
                    modern_entry["topic"] = topic
                    modern_entry["prev_topic"] = edit_history_event["prev_subject"]

                    # Because edit_history is ordered chronologically,
                    # most recent to least recent, we set the topic
                    # variable to the `prev_topic` value for this edit
                    # for any subsequent topic edits in the loop.
                    topic = edit_history_event["prev_subject"]

                elif "prev_topic" in edit_history_event:
                    # Add topic edit key/value pairs from modern format.
                    modern_entry["topic"] = topic
                    modern_entry["prev_topic"] = edit_history_event["prev_topic"]

                    # Same logic as above but for modern format.
                    topic = edit_history_event["prev_topic"]

                if "prev_stream" in edit_history_event:
                    # Add stream edit key/value pairs.
                    modern_entry["stream"] = stream_id
                    modern_entry["prev_stream"] = edit_history_event["prev_stream"]

                    # Same logic as above for the topic variable.
                    stream_id = edit_history_event["prev_stream"]

            modern_edit_history.append(modern_entry)

        message.edit_history = orjson.dumps(modern_edit_history).decode()

    message_model.objects.bulk_update(messages, ["edit_history"])


def copy_and_update_message_edit_history(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Message = apps.get_model("zerver", "Message")
    ArchivedMessage = apps.get_model("zerver", "ArchivedMessage")

    message_models = [Message, ArchivedMessage]
    for message_model in message_models:
        if not message_model.objects.filter(edit_history__isnull=False).exists():
            # No messages with "edit_history"
            continue

        first_id_to_update = message_model.objects.filter(edit_history__isnull=False).aggregate(
            Min("id")
        )["id__min"]

        last_id = message_model.objects.latest("id").id

        id_range_lower_bound = first_id_to_update
        id_range_upper_bound = first_id_to_update + BATCH_SIZE

        while id_range_upper_bound <= last_id:
            backfill_message_edit_history_chunk(
                id_range_lower_bound, id_range_upper_bound, message_model
            )
            print(f"Modernized edit history for {id_range_upper_bound}/{last_id} messages.")
            id_range_lower_bound = id_range_upper_bound + 1
            id_range_upper_bound = id_range_lower_bound + BATCH_SIZE
            time.sleep(0.1)

        if last_id >= id_range_lower_bound:
            # Copy/update for the last batch, or if only 1 message with edit_history in db
            backfill_message_edit_history_chunk(id_range_lower_bound, last_id, message_model)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0376_set_realmemoji_author_and_reupload_realmemoji"),
    ]

    operations = [
        migrations.RunPython(
            copy_and_update_message_edit_history,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
