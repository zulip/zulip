from __future__ import print_function

import os
import re
import ujson
from typing import Any, Dict, List

from django.core.management.commands import compilemessages
from django.conf import settings


class Command(compilemessages.Command):

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)
        self.extract_language_options()

    def extract_language_options(self):
        locale_path = "{}/locale".format(settings.STATIC_ROOT)
        output_path = "{}/language_options.json".format(locale_path)

        po_template = '{}/{}/LC_MESSAGES/django.po'
        data = {'languages': []}  # type: Dict[str, List[Dict[str, str]]]
        lang_name_re = re.compile('"Language-Team: (.*?) \(')

        locales = os.listdir(locale_path)
        locales.append('en')
        locales = list(set(locales))

        for locale in locales:
            info = {}
            if locale == 'en':
                data['languages'].append({'code': 'en', 'name': 'English'})
                continue
            if locale == 'zh_CN':
                name = 'Simplified Chinese'
            else:
                filename = po_template.format(locale_path, locale)
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
                        raise Exception("Unknown language")

            info['name'] = name
            info['code'] = locale

            if info:
                data['languages'].append(info)

        with open(output_path, 'w') as writer:
            ujson.dump(data, writer, indent=2)
