import json
import os
import re
from subprocess import CalledProcessError, check_output
from typing import Any, Dict, List

import orjson
import polib
from django.conf import settings
from django.conf.locale import LANG_INFO
from django.core.management.base import CommandParser
from django.core.management.commands import compilemessages
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from django.utils.translation import to_language
from pyuca import Collator

from scripts.setup.inline_email_css import get_css_inlined_list


class Command(compilemessages.Command):
    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)

        parser.add_argument(
            "--strict", "-s", action="store_true", help="Stop execution in case of errors."
        )

        parser.add_argument(
            "--log-inlined",
            "-li",
            action="store",
            help="""
            Use the --log-inlined flag to display POEntries that were inlined.
            Usage: -li=[LOCALE]. For example, run './manage.py compilemessages -li=en_GB'
            to view inlined entries for that specific locale.
            If no argument is specified, output will be generated for all languages.
            """,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        super().handle(*args, **options)
        self.strict = options["strict"]
        self.log_inlined = options["log_inlined"]
        self.extract_language_options()
        self.create_language_name_map()

    # This is a bit of a hack. Our email templates are preprocessed by
    # the inline_email_css tool to put `style` attributes on most HTML
    # elements before being passed to Django to send; this is
    # necessary because of email's very limited CSS support.
    #
    # In particular, this process adds style attributes to `<a>` tags
    # or other HTML elements that appear in translated blocks. This
    # breaks translations; our `.mo` file will contain translations
    # for the original source strings present in the `.source.html`
    # file, but Django needs translations for the processed strings
    # present in the compiled `.html` file.
    #
    # This function addresses this issue by processing the
    # translations to replace the original source/translated strings
    # in emails with the result of running the inline_email_css
    # tooling on both strings, and then write the result to the MO
    # file. (This is preferable to having translators work with
    # strings containing a bunch of hardcoded `style` attributes,
    # since we don't want to require translators to do extra work
    # whenever we change the email CSS).
    #
    # This allows Django to correctly translate the styled English
    # email into a styled translated email.
    def inline_strings_for_language(self, lc_messages_path: str) -> None:
        po_file = polib.pofile(f"{lc_messages_path}/django.po")
        entries_to_inline: List[polib.POEntry] = []

        # Identify strings that contain an HTML tag that are declared
        # in a `.source.html` email template.
        for entry in po_file:
            entry_in_email = any(
                "templates/zerver/emails/" in item[0] and item[0].endswith(".source.html")
                for item in entry.occurrences
            )
            # We check for `<` as a proxy for whether an HTML tags are
            # contained in the email.
            if entry_in_email and "<" in entry.msgid:
                entries_to_inline.append(polib.POEntry(msgid=entry.msgid, msgstr=entry.msgstr))

        inlined_entries = get_css_inlined_list(entries_to_inline)

        # The purpose of this code is to assist developers in testing the accuracy of string
        # templating. The code creates a new file, compiled.django.po, where all logged inlined
        # entries are stored.
        if self.log_inlined and self.log_inlined in lc_messages_path or self.log_inlined == "all":
            compiled_file_path = f"{lc_messages_path}/compiled.django.po"
            po = polib.POFile()
            po.extend(inlined_entries)
            po.save(compiled_file_path)
            print(f"Inlined strings are saved in {compiled_file_path}")

        # Add the inlined entries to the set of translated strings. We
        # could potentially save a bit of storage by dropping the
        # existing (useless) pre-translation entries, but some care
        # may be required to make sure they're only used in the email
        # files.
        po_file.extend(inlined_entries)

        # TODO: Ideally, we'd avoid writing the MO file twice (Django
        # will have already run it via the `super` hook).
        po_file.save_as_mofile(f"{lc_messages_path}/django.mo")

    def create_language_name_map(self) -> None:
        join = os.path.join
        deploy_root = settings.DEPLOY_ROOT
        path = join(deploy_root, "locale", "language_options.json")
        output_path = join(deploy_root, "locale", "language_name_map.json")

        with open(path, "rb") as reader:
            languages = orjson.loads(reader.read())
            lang_list = []
            for lang_info in languages["languages"]:
                lang_info["name"] = lang_info["name_local"]
                del lang_info["name_local"]
                lang_list.append(lang_info)

            collator = Collator()
            lang_list.sort(key=lambda lang: collator.sort_key(lang["name"]))

        with open(output_path, "wb") as output_file:
            output_file.write(
                orjson.dumps(
                    {"name_map": lang_list},
                    option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
                )
            )

    def get_po_filename(self, locale_path: str, locale: str) -> str:
        po_template = "{}/{}/LC_MESSAGES/django.po"
        return po_template.format(locale_path, locale)

    def get_json_filename(self, locale_path: str, locale: str) -> str:
        return f"{locale_path}/{locale}/translations.json"

    def get_name_from_po_file(self, po_filename: str, locale: str) -> str:
        try:
            team = polib.pofile(po_filename).metadata["Language-Team"]
            return team[: team.rindex(" (")]
        except (KeyError, ValueError):
            raise Exception(f"Unknown language {locale}")

    def get_locales(self) -> List[str]:
        output = check_output(["git", "ls-files", "locale"], text=True)
        tracked_files = output.split()
        regex = re.compile(r"locale/(\w+)/LC_MESSAGES/django.po")
        locales = ["en"]
        for tracked_file in tracked_files:
            matched = regex.search(tracked_file)
            if matched:
                locales.append(matched.group(1))

        return locales

    def extract_language_options(self) -> None:
        locale_path = f"{settings.DEPLOY_ROOT}/locale"
        output_path = f"{locale_path}/language_options.json"

        data: Dict[str, List[Dict[str, Any]]] = {"languages": []}

        try:
            locales = self.get_locales()
        except CalledProcessError:
            # In case we are not under a Git repo, fallback to getting the
            # locales using listdir().
            locales = os.listdir(locale_path)
            locales.append("en")
            locales = list(set(locales))

        for locale in sorted(locales):
            if locale == "en":
                data["languages"].append(
                    {
                        "name": "English",
                        "name_local": "English",
                        "code": "en",
                        "locale": "en",
                    }
                )
                continue

            lc_messages_path = os.path.join(locale_path, locale, "LC_MESSAGES")
            if not os.path.exists(lc_messages_path):
                # Not a locale.
                continue

            info: Dict[str, Any] = {}
            code = to_language(locale)
            percentage = self.get_translation_percentage(locale_path, locale)

            # CSS inlining for specific strings that occur in templates/zerver/emails.
            self.inline_strings_for_language(lc_messages_path)
            try:
                name = LANG_INFO[code]["name"]
                name_local = LANG_INFO[code]["name_local"]
            except KeyError:
                # Fallback to getting the name from PO file.
                filename = self.get_po_filename(locale_path, locale)
                name = self.get_name_from_po_file(filename, locale)
                with override_language(code):
                    name_local = _(name)

            info["name"] = name
            info["name_local"] = name_local
            info["code"] = code
            info["locale"] = locale
            info["percent_translated"] = percentage
            data["languages"].append(info)

        with open(output_path, "w") as writer:
            json.dump(data, writer, indent=2, sort_keys=True)
            writer.write("\n")

    def get_translation_percentage(self, locale_path: str, locale: str) -> int:
        # backend stats
        po = polib.pofile(self.get_po_filename(locale_path, locale))
        not_translated = len(po.untranslated_entries())
        total = len(po.translated_entries()) + not_translated

        # frontend stats
        with open(self.get_json_filename(locale_path, locale), "rb") as reader:
            for key, value in orjson.loads(reader.read()).items():
                total += 1
                if value == "":
                    not_translated += 1

        # mobile stats
        with open(os.path.join(locale_path, "mobile_info.json"), "rb") as mob:
            mobile_info = orjson.loads(mob.read())
        try:
            info = mobile_info[locale]
        except KeyError:
            if self.strict:
                raise
            info = {"total": 0, "not_translated": 0}

        total += info["total"]
        not_translated += info["not_translated"]

        return (total - not_translated) * 100 // total
