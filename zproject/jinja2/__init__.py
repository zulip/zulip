from __future__ import absolute_import  # Python 2 only

from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.defaultfilters import slugify, pluralize
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils import translation
from django.http import HttpResponse
from jinja2 import Environment

from .compressors import compressed_css, minified_js
from zerver.templatetags.app_filters import display_list


def render_to_response(*args, **kwargs):
    response = render_to_string(*args, **kwargs)
    return HttpResponse(response)


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
        'compressed_css': compressed_css,
        'minified_js': minified_js,
    })

    env.install_gettext_translations(translation, True)

    env.filters['slugify'] = slugify
    env.filters['pluralize'] = pluralize
    env.filters['display_list'] = display_list

    return env
