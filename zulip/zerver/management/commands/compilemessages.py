from __future__ import print_function

import os
import re
import ujson

from six import text_type
from typing import Any, Dict, List

from django.core.management.commands import compilemessages
from django.conf import settings

import polib

class Command(compilemessages.Command):

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        super(Command, self).handle(*args, **options)
        self.extract_language_options()

    def get_po_filename(self, locale_path, locale):
        # type: (text_type, text_type) -> text_type
        po_template = '{}/{}/LC_MESSAGES/django.po'
        return po_template.format(locale_path, locale)

    def get_json_filename(self, locale_path, locale):
        # type: (text_type, text_type) -> text_type
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
            if locale == u'zh-CN':
                continue
            if locale == u'zh_CN':
                name = u'Simplified Chinese'
            else:
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
        # type: (text_type, text_type) -> int

        # backend stats
        po = polib.pofile(self.get_po_filename(locale_path, locale))
        not_translated = len(po.untranslated_entries())
        total = len(po.translated_entries()) + not_translated

        # There is a difference between frontend and backend files for Chinese
        if locale == 'zh_CN':
            locale = 'zh-CN'

        # frontend stats
        with open(self.get_json_filename(locale_path, locale)) as reader:
            for key, value in ujson.load(reader).items():
                total += 1
                if key == value:
                    not_translated += 1

        return (total - not_translated) * 100 // total
