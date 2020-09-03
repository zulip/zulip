from typing import Any

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.defaultfilters import pluralize, slugify
from django.urls import reverse
from django.utils import translation
from django.utils.timesince import timesince
from jinja2 import Environment
from two_factor.templatetags.two_factor import device_action

from zerver.templatetags.app_filters import display_list, render_markdown_path


def environment(**options: Any) -> Environment:
    env = Environment(**options)
    env.globals.update(
        default_page_params={
            'debug_mode': False,
            'webpack_public_path': staticfiles_storage.url(
                settings.WEBPACK_LOADER['DEFAULT']['BUNDLE_DIR_NAME'],
            ),
        },
        static=staticfiles_storage.url,
        url=reverse,
        render_markdown_path=render_markdown_path,
    )

    env.install_gettext_translations(translation, True)

    env.filters['slugify'] = slugify
    env.filters['pluralize'] = pluralize
    env.filters['display_list'] = display_list
    env.filters['device_action'] = device_action
    env.filters['timesince'] = timesince

    return env
