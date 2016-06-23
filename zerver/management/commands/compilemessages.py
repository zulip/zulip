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
        DEPLOY_ROOT = settings.DEPLOY_ROOT

        output_path = "{}/static/locale/language_options.json".format(DEPLOY_ROOT)
        locale_path = "{}/locale".format(DEPLOY_ROOT)

        po_template = '{}/{}/LC_MESSAGES/django.po'
        data = {'languages': []}  # type: Dict[str, List[Dict[str, str]]]
        lang_name_re = re.compile('"Language-Team: (.*?) \(')

        for locale in os.listdir(locale_path):
            info = {}
            if locale == 'en':
                data['languages'].append({'code': 'en', 'name': 'English'})
                continue
            if locale == 'zh_CN':
                name = 'Simplified Chinese'
            else:
                filename = po_template.format(locale_path, locale)
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
            ujson.dump(data, writer)
