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


class Command(compilemessages.Command):
    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)

        parser.add_argument(
            "--strict", "-s", action="store_true", help="Stop execution in case of errors."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        super().handle(*args, **options)
        self.strict = options["strict"]
        self.extract_language_options()
        self.create_language_name_map()

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
