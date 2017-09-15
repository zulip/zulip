# -*- coding: utf-8 -*-
from __future__ import absolute_import
import operator

from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext as _
from django.utils.lru_cache import lru_cache

from six.moves import urllib, zip_longest, zip, range
from typing import Any, List, Dict, Optional, Text

import os
import ujson

def with_language(string, language):
    # type: (Text, Text) -> Text
    """
    This is an expensive function. If you are using it in a loop, it will
    make your code slow.
    """
    old_language = translation.get_language()
    translation.activate(language)
    result = _(string)
    translation.activate(old_language)
    return result

@lru_cache()
def get_language_list():
    # type: () -> List[Dict[str, Any]]
    path = os.path.join(settings.STATIC_ROOT, 'locale', 'language_name_map.json')
    with open(path, 'r') as reader:
        languages = ujson.load(reader)
        return languages['name_map']

def get_language_list_for_templates(default_language):
    # type: (Text) -> List[Dict[str, Dict[str, str]]]
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
    # type: (str) -> Optional[Text]
    for lang in get_language_list():
        if lang['code'] == code:
            return lang['name']
    return None

def get_available_language_codes():
    # type: () -> List[Text]
    language_list = get_language_list()
    codes = [language['code'] for language in language_list]
    return codes
