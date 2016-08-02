# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext as _

from six import text_type
from typing import Any, List, Dict, Optional

import os
import ujson

def with_language(string, language):
    # type: (text_type, text_type) -> text_type
    old_language = translation.get_language()
    translation.activate(language)
    result = _(string)
    translation.activate(old_language)
    return result

def get_language_list():
    # type: () -> List[Dict[str, Any]]
    path = os.path.join(settings.STATIC_ROOT, 'locale', 'language_options.json')
    with open(path, 'r') as reader:
        languages = ujson.load(reader)
        lang_list = []
        for lang_info in languages['languages']:
            name = lang_info['name']
            lang_info['name'] = with_language(name, lang_info['code'])
            lang_list.append(lang_info)

        return sorted(lang_list, key=lambda i: i['name'])

def get_language_name(code):
    # type: (str) -> Optional[text_type]
    for lang in get_language_list():
        if lang['code'] == code:
            return lang['name']

def get_available_language_codes():
    # type: () -> List[text_type]
    language_list = get_language_list()
    codes = [language['code'] for language in language_list]
    return codes
