# See https://zulip.readthedocs.io/en/latest/translating/internationalization.html

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import orjson
from django.conf import settings
from django.http import HttpRequest
from django.utils import translation


@lru_cache()
def get_language_list() -> List[Dict[str, Any]]:
    path = os.path.join(settings.DEPLOY_ROOT, "locale", "language_name_map.json")
    with open(path, "rb") as reader:
        languages = orjson.loads(reader.read())
        return languages["name_map"]


def get_language_name(code: str) -> str:
    for lang in get_language_list():
        if code in (lang["code"], lang["locale"]):
            return lang["name"]
    # Log problem, but still return a name
    logging.error("Unknown language code '%s'", code)
    return "Unknown"


def get_available_language_codes() -> List[str]:
    language_list = get_language_list()
    codes = [language["code"] for language in language_list]
    return codes


def get_language_translation_data(language: str) -> Dict[str, str]:
    if language == "en":
        return {}
    locale = translation.to_locale(language)
    path = os.path.join(settings.DEPLOY_ROOT, "locale", locale, "translations.json")
    try:
        with open(path, "rb") as reader:
            return orjson.loads(reader.read())
    except FileNotFoundError:
        print(f"Translation for {language} not found at {path}")
        return {}


def get_and_set_request_language(
    request: HttpRequest, user_configured_language: str, testing_url_language: Optional[str] = None
) -> str:
    # We pick a language for the user as follows:
    # * First priority is the language in the URL, for debugging.
    # * If not in the URL, we use the language from the user's settings.
    request_language = testing_url_language
    if request_language is None:
        request_language = user_configured_language
    translation.activate(request_language)

    # We also want to save the language to the user's cookies, so that
    # something reasonable will happen in logged-in portico pages.
    # We accomplish that by setting a flag on the request which signals
    # to LocaleMiddleware to set the cookie on the response.
    request._set_language = translation.get_language()

    return request_language
