import csv
import os
import queue
import shutil
from argparse import ArgumentParser
from collections.abc import Iterator
from datetime import datetime, timezone
from email.headerregistry import Address
from functools import lru_cache, reduce
from operator import or_
from threading import Lock, Thread
from typing import Any, NoReturn, Union

from django.conf import settings
from django.core.management.base import CommandError
from django.db.models import Q
from typing_extensions import override

from zerver.lib.export import orjson_stream
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.soft_deactivation import reactivate_user_if_soft_deactivated
from zerver.lib.upload import save_attachment_contents
from zerver.models import AbstractUserMessage, Message, Recipient, Stream, UserProfile
from zerver.models.recipients import get_direct_message_group, get_or_create_direct_message_group
from zerver.models.streams import get_stream
from zerver.models.users import get_user_by_delivery_email

check_lock = Lock()
download_queue: queue.Queue[str] = queue.Queue()
BATCH_SIZE = 1000


def write_attachment(base_path: str, path_id: str, file_lock: Union["Lock", None] = None) -> None:
    dir_path_id = os.path.dirname(path_id)
    assert "../" not in dir_path_id
    os.makedirs(base_path + "/" + dir_path_id, exist_ok=True)
    with open(base_path + "/" + path_id, "wb") as attachment_file:
        if file_lock:
            file_lock.release()
        save_attachment_contents(path_id, attachment_file)


def download_worker(base_path: str) -> NoReturn:
    while True:
        path_id = download_queue.get()

        check_lock.acquire()
        if os.path.exists(base_path + "/" + path_id):
            check_lock.release()
            download_queue.task_done()
            continue

        print(f"({download_queue.qsize()} Downloading {path_id}")
        write_attachment(base_path, path_id, check_lock)
        download_queue.task_done()


class Command(ZulipBaseCommand):
    help = """Exports the messages matching certain search terms, or from
senders/recipients.

This is most often used for legal compliance.
"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument(
            "--output",
            metavar="<path>",
            help="File to output JSON/CSV results to; it must not exist, unless --force is given",
            required=True,
        )
        parser.add_argument(
            "--write-attachments",
            metavar="<directory>",
            help="If provided, export all referenced attachments into the directory",
        )
        parser.add_argument(
            "--force", action="store_true", help="Overwrite the output file if it exists already"
        )
        parser.add_argument("--threads", default=5, type=int)

        parser.add_argument(
            "--file",
            metavar="<path>",
            help="Read search terms from the named file, one per line",
        )
        parser.add_argument(
            "search_terms",
            nargs="*",
            metavar="<search term>",
            help="Terms to search for in message body or topic",
        )
        parser.add_argument(
            "--after",
            metavar="<datetime>",
            help="Limit to messages on or after this ISO datetime, treated as UTC",
            type=lambda s: datetime.fromisoformat(s).astimezone(timezone.utc),
        )
        parser.add_argument(
            "--before",
            metavar="<datetime>",
            help="Limit to messages on or before this ISO datetime, treated as UTC",
            type=lambda s: datetime.fromisoformat(s).astimezone(timezone.utc),
        )
        source_dest = parser.add_mutually_exclusive_group()

        source_dest.add_argument(
            "--sender",
            action="append",
            metavar="<email>",
            help="Limit to messages sent by users with any of these emails (may be specified more than once)",
        )
        source_dest.add_argument(
            "--recipient",
            action="append",
            metavar="<email>",
            help="Limit to messages received by users with any of these emails (may be specified more than once).  This is a superset of --sender, since senders receive every message they send.",
        )
        source_dest.add_argument(
            "--dm",
            action="append",
            metavar="<email>",
            help="Limit to messages in a DM between all of the users provided.",
        )
        source_dest.add_argument(
            "--channel",
            action="append",
            metavar="<channel-name>",
            help="Limit to messages in the given channel.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        terms = set()
        if options["file"]:
            with open(options["file"]) as f:
                terms.update(f.read().splitlines())
        terms.update(options["search_terms"])

        if (
            not terms
            and not options["before"]
            and not options["after"]
            and not options["sender"]
            and not options["recipient"]
            and not options["dm"]
            and not options["channel"]
        ):
            raise CommandError("One or more limits are required!")

        if not options["output"].endswith((".json", ".csv")):
            raise CommandError(
                "Unknown file format: {options['output']}  Only .csv and .json are supported"
            )

        if os.path.exists(options["output"]) and not options["force"]:
            raise CommandError(
                f"Output path '{options['output']}' already exists; use --force to overwrite"
            )

        if options["write_attachments"] and os.path.exists(options["write_attachments"]):
            if not options["force"]:
                raise CommandError(
                    f"Attachments output path '{options['write_attachments']}' already exists; use --force to overwrite"
                )
            shutil.rmtree(options["write_attachments"])

        realm = self.get_realm(options)
        assert realm is not None
        need_distinct = False
        usermessage_joined = False
        limits = Q()

        limits = reduce(
            or_,
            [
                Q(content__icontains=term) | Q(is_channel_message=True, subject__icontains=term)
                for term in terms
            ],
            limits,
        )

        if options["after"]:
            limits &= Q(date_sent__gt=options["after"])
        if options["before"]:
            limits &= Q(date_sent__lt=options["before"])
        if options["recipient"]:
            user_profiles = [get_user_by_delivery_email(e, realm) for e in options["recipient"]]
            for user_profile in user_profiles:
                # Users need to not be long-term idle for the
                # UserMessages to be a judge of which messages they
                # received.
                reactivate_user_if_soft_deactivated(user_profile)
            limits &= Q(
                usermessage__user_profile_id__in=[user_profile.id for user_profile in user_profiles]
            )
            need_distinct = len(user_profiles) > 1
            usermessage_joined = True
        elif options["sender"]:
            limits &= reduce(
                or_,
                [Q(sender__delivery_email__iexact=e) for e in options["sender"]],
            )
        elif options["dm"]:
            user_profiles = [get_user_by_delivery_email(e, realm) for e in options["dm"]]
            for user_profile in user_profiles:
                reactivate_user_if_soft_deactivated(user_profile)
            if len(user_profiles) == 1:
                limits &= Q(
                    usermessage__user_profile_id=user_profiles[0].id,
                    usermessage__flags__andnz=AbstractUserMessage.flags.is_private.mask,
                )
                usermessage_joined = True
            elif len(user_profiles) == 2:
                user_a, user_b = user_profiles
                direct_message_group = get_direct_message_group(id_list=[user_a.id, user_b.id])
                if direct_message_group and settings.PREFER_DIRECT_MESSAGE_GROUP:
                    limits &= Q(recipient=direct_message_group.recipient)
                else:
                    limits &= Q(recipient=user_a.recipient, sender=user_b) | Q(
                        recipient=user_b.recipient, sender=user_a
                    )
            else:
                direct_message_group = get_or_create_direct_message_group(
                    [user.id for user in user_profiles]
                )
                limits &= Q(recipient=direct_message_group.recipient)
        elif options["channel"]:
            channels = [get_stream(n.lstrip("#"), realm) for n in options["channel"]]
            limits &= Q(recipient__in=[s.recipient_id for s in channels])

        messages_query = (
            Message.objects.filter(limits, realm=realm)
            .select_related("sender")
            .only(
                "id",
                "date_sent",
                "sender__full_name",
                "sender__delivery_email",
                "recipient_id",
                "subject",
                "content",
                "edit_history",
                "has_attachment",
            )
            .order_by("id")
        )
        if need_distinct:
            messages_query = messages_query.distinct("id")

        if options["write_attachments"]:
            for i in range(options["threads"]):
                Thread(
                    target=download_worker, daemon=True, args=(options["write_attachments"],)
                ).start()

        @lru_cache(maxsize=1000)
        def format_sender(full_name: str, delivery_email: str) -> str:
            return str(Address(display_name=full_name, addr_spec=delivery_email))

        def format_full_recipient(recipient_id: int, subject: str) -> str:
            recip_str, has_subject = format_recipient(recipient_id)
            if not has_subject:
                return recip_str
            return f"{recip_str} > {subject}"

        @lru_cache(maxsize=1000)
        def format_recipient(recipient_id: int) -> tuple[str, bool]:
            recipient = Recipient.objects.get(id=recipient_id)

            if recipient.type == Recipient.STREAM:
                stream = Stream.objects.values("name").get(id=recipient.type_id)
                return "#" + stream["name"], True

            users = (
                UserProfile.objects.filter(
                    subscription__recipient_id=recipient.id,
                )
                .order_by("full_name")
                .values_list("full_name", "delivery_email")
            )

            return ", ".join(format_sender(e[0], e[1]) for e in users), False

        def transform_message(message: Message) -> dict[str, str]:
            row = {
                "id": str(message.id),
                "timestamp (UTC)": message.date_sent.astimezone(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "sender": format_sender(message.sender.full_name, message.sender.delivery_email),
                "recipient": format_full_recipient(message.recipient_id, message.subject),
                "content": message.content,
                "edit history": message.edit_history if message.edit_history is not None else "",
            }
            if options["write_attachments"]:
                if message.has_attachment:
                    attachments = message.attachment_set.all()
                    row["attachments"] = " ".join(a.path_id for a in attachments)
                    for attachment in attachments:
                        download_queue.put(attachment.path_id)
                else:
                    row["attachments"] = ""
            return row

        def chunked_results() -> Iterator[dict[str, str]]:
            min_id = 0
            while True:
                batch_query = messages_query.filter(id__gt=min_id)
                if usermessage_joined:
                    batch_query = batch_query.extra(
                        where=["zerver_usermessage.message_id > %s"], params=[min_id]
                    )
                batch = [transform_message(m) for m in batch_query[:BATCH_SIZE]]
                if len(batch) == 0:
                    break
                min_id = int(batch[-1]["id"])
                print(".")
                yield from batch

        print("Exporting messages...")
        if options["output"].endswith(".json"):
            with open(options["output"], "wb") as json_file:
                json_file.writelines(orjson_stream(chunked_results()))
        elif options["output"].endswith(".csv"):
            with open(options["output"], "w") as csv_file:
                columns = [
                    "id",
                    "timestamp (UTC)",
                    "sender",
                    "recipient",
                    "content",
                    "edit history",
                ]

                if options["write_attachments"]:
                    columns += ["attachments"]
                csvwriter = csv.DictWriter(csv_file, columns)
                csvwriter.writeheader()
                csvwriter.writerows(chunked_results())
        download_queue.join()
