import csv
import os
from argparse import ArgumentParser
from datetime import datetime, timezone
from email.headerregistry import Address
from functools import lru_cache, reduce
from operator import or_
from typing import Any, Dict, Tuple

import orjson
from django.core.management.base import CommandError
from django.db.models import Q

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.soft_deactivation import reactivate_user_if_soft_deactivated
from zerver.models import Message, Recipient, Stream, UserProfile, get_user_by_delivery_email


class Command(ZulipBaseCommand):
    help = """Exports the messages matching certain search terms, or from
senders/recipients.

This is most often used for legal compliance.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument(
            "--output",
            metavar="<path>",
            help="File to output JSON/CSV results to; it must not exist, unless --force is given",
            required=True,
        )
        parser.add_argument(
            "--force", action="store_true", help="Overwrite the output file if it exists already"
        )

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
        users = parser.add_mutually_exclusive_group()
        users.add_argument(
            "--sender",
            action="append",
            metavar="<email>",
            help="Limit to messages sent by users with any of these emails (may be specified more than once)",
        )
        users.add_argument(
            "--recipient",
            action="append",
            metavar="<email>",
            help="Limit to messages received by users with any of these emails (may be specified more than once).  This is a superset of --sender, since senders receive every message they send.",
        )

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

        realm = self.get_realm(options)
        assert realm is not None
        limits = Q()

        limits = reduce(
            or_,
            [Q(content__icontains=term) | Q(subject__icontains=term) for term in terms],
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
        elif options["sender"]:
            limits &= reduce(
                or_,
                [Q(sender__delivery_email__iexact=e) for e in options["sender"]],
            )

        messages_query = Message.objects.filter(limits, realm=realm).order_by("date_sent")
        print(f"Exporting {len(messages_query)} messages...")

        @lru_cache(maxsize=1000)
        def format_sender(full_name: str, delivery_email: str) -> str:
            return str(Address(display_name=full_name, addr_spec=delivery_email))

        def format_full_recipient(recipient_id: int, subject: str) -> str:
            recip_str, has_subject = format_recipient(recipient_id)
            if not has_subject:
                return recip_str
            return f"{recip_str} > {subject}"

        @lru_cache(maxsize=1000)
        def format_recipient(recipient_id: int) -> Tuple[str, bool]:
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

            return ", ".join([format_sender(e[0], e[1]) for e in users]), False

        def transform_message(message: Message) -> Dict[str, str]:
            return {
                "id": str(message.id),
                "timestamp (UTC)": message.date_sent.astimezone(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "sender": format_sender(message.sender.full_name, message.sender.delivery_email),
                "recipient": format_full_recipient(message.recipient_id, message.subject),
                "content": message.content,
                "edit history": message.edit_history if message.edit_history is not None else "",
            }

        if options["output"].endswith(".json"):
            with open(options["output"], "wb") as json_file:
                json_file.write(
                    # orjson doesn't support dumping from a generator
                    orjson.dumps(
                        [transform_message(m) for m in messages_query], option=orjson.OPT_INDENT_2
                    )
                )
        elif options["output"].endswith(".csv"):
            with open(options["output"], "w") as csv_file:
                csvwriter = csv.DictWriter(
                    csv_file,
                    ["id", "timestamp (UTC)", "sender", "recipient", "content", "edit history"],
                )
                csvwriter.writeheader()
                csvwriter.writerows(transform_message(m) for m in messages_query)
