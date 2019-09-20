from typing import Any

from django.template.defaultfilters import slugify, pluralize
from django.urls import reverse
from django.utils import translation
from django.utils.timesince import timesince
from jinja2 import Environment
from two_factor.templatetags.two_factor import device_action

from zerver.templatetags.app_filters import display_list, render_markdown_path, dump_example


def environment(**options: Any) -> Environment:
    env = Environment(**options)
    env.globals.update({
        'url': reverse,
        'render_markdown_path': render_markdown_path,
        'dump_example': dump_example,
    })

    env.install_gettext_translations(translation, True)

    env.filters['slugify'] = slugify
    env.filters['pluralize'] = pluralize
    env.filters['display_list'] = display_list
    env.filters['device_action'] = device_action
    env.filters['timesince'] = timesince

    return env
