import os
from argparse import ArgumentParser
from datetime import datetime, timezone
from email.headerregistry import Address
from functools import lru_cache, reduce
from operator import or_
from typing import Any

from django.core.management.base import CommandError
from django.db.models import Q
from django.forms.models import model_to_dict

from zerver.lib.export import floatify_datetime_fields, write_table_data
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Message, Recipient, Stream, UserProfile

ignore_keys = [
    "realm",
    "rendered_content_version",
    "sending_client",
    "search_tsvector",
]


class Command(ZulipBaseCommand):
    help = """Exports the messages matching certain search terms.

This is most often used for legal compliance.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument(
            "--output",
            metavar="<path>",
            help="File to output JSON results to; it must not exist, unless --force is given",
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
        parser.add_argument(
            "--sender",
            action="append",
            metavar="<email>",
            help="Limit to messages sent by users with any of these emails (may be specified more than once)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        terms = set()
        if options["file"]:
            with open(options["file"]) as f:
                terms.update(f.read().splitlines())
        terms.update(options["search_terms"])

        if not terms and not options["before"] and not options["after"]:
            raise CommandError("One or more limits are required!")

        if os.path.exists(options["output"]) and not options["force"]:
            raise CommandError(
                f"Output path '{options['output']}' already exists; use --force to overwrite"
            )

        realm = self.get_realm(options)
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
        if options["sender"]:
            print(options["sender"])
            limits &= reduce(
                or_,
                [Q(sender__delivery_email__iexact=e) for e in options["sender"]],
            )

        messages_query = Message.objects.filter(limits, realm=realm).order_by("date_sent")

        def format_sender(full_name: str, delivery_email: str) -> str:
            return str(Address(display_name=full_name, addr_spec=delivery_email))

        @lru_cache(maxsize=None)
        def format_recipient(recipient_id: int) -> str:
            recipient = Recipient.objects.get(id=recipient_id)

            if recipient.type == Recipient.STREAM:
                stream = Stream.objects.values("name").get(id=recipient.type_id)
                return "#" + stream["name"]

            users = (
                UserProfile.objects.filter(
                    subscription__recipient_id=recipient.id,
                )
                .order_by("full_name")
                .values_list("full_name", "delivery_email")
            )

            return ", ".join([format_sender(e[0], e[1]) for e in users])

        message_dicts = []
        for message in messages_query:
            item = model_to_dict(message)
            item["recipient_name"] = format_recipient(message.recipient_id)
            item["sender_name"] = format_sender(
                message.sender.full_name, message.sender.delivery_email
            )
            for key in ignore_keys:
                del item[key]

            message_dicts.append(item)

        output = {"zerver_message": message_dicts}
        floatify_datetime_fields(output, "zerver_message")
        for item in output["zerver_message"]:
            item["date_sent_utc"] = datetime.utcfromtimestamp(int(item["date_sent"])).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        write_table_data(options["output"], output)
