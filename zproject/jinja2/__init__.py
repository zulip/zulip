from typing import Any

import orjson
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.defaultfilters import pluralize, slugify
from django.urls import reverse
from django.utils import translation
from django.utils.timesince import timesince
from jinja2 import Environment
from two_factor.plugins.phonenumber.templatetags.phonenumber import device_action

from zerver.context_processors import DEFAULT_PAGE_PARAMS
from zerver.lib.send_email import FromAddress
from zerver.lib.templates import display_list, render_markdown_path, webpack_entry


def json_dumps(obj: object) -> str:
    return orjson.dumps(obj).decode()


def environment(**options: Any) -> Environment:
    env = Environment(autoescape=options.pop("autoescape", True), **options)
    env.globals.update(
        # default_page_params is provided here for responses where
        # zulip_default_context is not run, including the 404.html and
        # 500.html error pages.
        default_page_params=DEFAULT_PAGE_PARAMS,
        static=staticfiles_storage.url,
        url=reverse,
        render_markdown_path=render_markdown_path,
        webpack_entry=webpack_entry,
        support_email=FromAddress.SUPPORT,
    )

    env.install_gettext_translations(translation, True)  # type: ignore[attr-defined] # Added by jinja2.ext.i18n

    env.filters["slugify"] = slugify
    env.filters["pluralize"] = pluralize
    env.filters["display_list"] = display_list
    env.filters["device_action"] = device_action
    env.filters["timesince"] = timesince

    env.policies["json.dumps_function"] = json_dumps
    env.policies["json.dumps_kwargs"] = {}

    return env
