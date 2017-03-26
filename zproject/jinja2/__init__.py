from __future__ import absolute_import  # Python 2 only

from typing import Any

from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.defaultfilters import slugify, pluralize
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils import translation
from django.http import HttpResponse
from jinja2 import Environment

from .compressors import minified_js
from zerver.templatetags.app_filters import display_list, render_markdown_path


def environment(**options):
    # type: (**Any) -> Environment
    env = Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
        'minified_js': minified_js,
    })

    env.install_gettext_translations(translation, True)  # type: ignore # https://github.com/python/typeshed/issues/927

    env.filters['slugify'] = slugify
    env.filters['pluralize'] = pluralize
    env.filters['display_list'] = display_list
    env.filters['render_markdown_path'] = render_markdown_path

    return env
