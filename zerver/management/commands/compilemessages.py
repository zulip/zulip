from __future__ import print_function

import os
import re
import ujson

from typing import Any, Dict, List, Text

from django.core.management.commands import compilemessages
from django.conf import settings

import polib

from zerver.lib.i18n import with_language

class Command(compilemessages.Command):

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        if settings.PRODUCTION:
            # HACK: When using upgrade-zulip-from-git, we're in a
            # production environment where STATIC_ROOT will include
            # past versions; this ensures we only process the current
            # version
            settings.STATIC_ROOT = os.path.join(settings.DEPLOY_ROOT, "static")
            settings.LOCALE_PATHS = (os.path.join(settings.DEPLOY_ROOT, 'static/locale'),)
        super(Command, self).handle(*args, **options)
        self.extract_language_options()
        self.create_language_name_map()

    def create_language_name_map(self):
        # type: () -> None
        join = os.path.join
        static_root = settings.STATIC_ROOT
        path = join(static_root, 'locale', 'language_options.json')
        output_path = join(static_root, 'locale', 'language_name_map.json')

        with open(path, 'r') as reader:
            languages = ujson.load(reader)
            lang_list = []
            for lang_info in languages['languages']:
                name = lang_info['name']
                lang_info['name'] = with_language(name, lang_info['code'])
                lang_list.append(lang_info)

            lang_list.sort(key=lambda lang: lang['name'])

        with open(output_path, 'w') as output_file:
            ujson.dump({'name_map': lang_list}, output_file, indent=4)

    def get_po_filename(self, locale_path, locale):
        # type: (Text, Text) -> Text
        po_template = '{}/{}/LC_MESSAGES/django.po'
        return po_template.format(locale_path, locale)

    def get_json_filename(self, locale_path, locale):
        # type: (Text, Text) -> Text
        return "{}/{}/translations.json".format(locale_path, locale)

    def extract_language_options(self):
        # type: () -> None
        locale_path = u"{}/locale".format(settings.STATIC_ROOT)
        output_path = u"{}/language_options.json".format(locale_path)

        data = {'languages': []}  # type: Dict[str, List[Dict[str, Any]]]
        lang_name_re = re.compile('"Language-Team: (.*?) \(')

        locales = os.listdir(locale_path)
        locales.append(u'en')
        locales = list(set(locales))

        for locale in locales:
            info = {}  # type: Dict[str, Any]
            if locale == u'en':
                data['languages'].append({
                    'code': u'en',
                    'name': u'English',
                })
                continue
            filename = self.get_po_filename(locale_path, locale)
            if not os.path.exists(filename):
                continue

            with open(filename, 'r') as reader:
                result = lang_name_re.search(reader.read())
                if result:
                    try:
                        name = result.group(1)
                    except Exception:
                        print("Problem in parsing {}".format(filename))
                        raise
                else:
                    raise Exception("Unknown language %s" % (locale,))

            percentage = self.get_translation_percentage(locale_path, locale)

            info['name'] = name
            info['code'] = locale
            info['percent_translated'] = percentage

            if info:
                data['languages'].append(info)

        with open(output_path, 'w') as writer:
            ujson.dump(data, writer, indent=2)

    def get_translation_percentage(self, locale_path, locale):
        # type: (Text, Text) -> int

        # backend stats
        po = polib.pofile(self.get_po_filename(locale_path, locale))
        not_translated = len(po.untranslated_entries())
        total = len(po.translated_entries()) + not_translated

        # frontend stats
        with open(self.get_json_filename(locale_path, locale)) as reader:
            for key, value in ujson.load(reader).items():
                total += 1
                if key == value:
                    not_translated += 1

        return (total - not_translated) * 100 // total
