# -*- coding: utf-8 -*-
import operator

from django.conf import settings
from django.utils import translation
from django.utils.translation import ugettext as _
from django.utils.lru_cache import lru_cache

from itertools import zip_longest
from typing import Any, List, Dict, Optional

import os
import ujson

def with_language(string: str, language: str) -> str:
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
def get_language_list() -> List[Dict[str, Any]]:
    path = os.path.join(settings.STATIC_ROOT, 'locale', 'language_name_map.json')
    with open(path, 'r') as reader:
        languages = ujson.load(reader)
        return languages['name_map']

def get_language_list_for_templates(default_language: str) -> List[Dict[str, Dict[str, str]]]:
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
                percent = "{} ({}%)".format(name, lang['percent_translated'])

            selected = False
            if default_language in (lang['code'], lang['locale']):
                selected = True

            item[position] = {
                'name': name,
                'code': lang['code'],
                'percent': percent,
                'selected': selected
            }

        formatted_list.append(item)

    return formatted_list

def get_language_name(code: str) -> Optional[str]:
    for lang in get_language_list():
        if code in (lang['code'], lang['locale']):
            return lang['name']
    return None

def get_available_language_codes() -> List[str]:
    language_list = get_language_list()
    codes = [language['code'] for language in language_list]
    return codes

def get_language_translation_data(language: str) -> Dict[str, str]:
    if language == 'zh-hans':
        language = 'zh_Hans'
    elif language == 'zh-hant':
        language = 'zh_Hant'
    elif language == 'id-id':
        language = 'id_ID'
    path = os.path.join(settings.STATIC_ROOT, 'locale', language, 'translations.json')
    try:
        with open(path, 'r') as reader:
            return ujson.load(reader)
    except FileNotFoundError:
        print('Translation for {} not found at {}'.format(language, path))
        return {}
