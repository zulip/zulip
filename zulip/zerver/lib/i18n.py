# -*- coding: utf-8 -*-
from __future__ import absolute_import
import operator

from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext as _

from six import text_type
from six.moves import urllib, zip_longest, zip, range
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

def get_language_list_for_templates(default_language):
    # type: (text_type) -> List[Dict[str, Dict[str, str]]]
    language_list = [l for l in get_language_list()
                     if 'percent_translated' not in l or
                        l['percent_translated'] >= 5.]

    formatted_list = []
    lang_len = len(language_list)
    firsts_end = (lang_len // 2) + operator.mod(lang_len, 2)
    firsts = list(range(0, firsts_end))
    seconds = list(range(firsts_end, lang_len))
    assert len(firsts) + len(seconds) == lang_len
    for row in zip_longest(firsts, seconds):
        item = {}
        for position, ind in zip(['first', 'second'], row):
            if ind is None:
                continue

            lang = language_list[ind]
            percent = name = lang['name']
            if 'percent_translated' in lang:
                percent = u"{} ({}%)".format(name, lang['percent_translated'])

            item[position] = {
                'name': name,
                'code': lang['code'],
                'percent': percent,
                'selected': True if default_language == lang['code'] else False
            }

        formatted_list.append(item)

    return formatted_list

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
