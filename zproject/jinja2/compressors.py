"""
`minified_js` is taken from `zerver.templatetags.minified_js.py`
"""
from __future__ import absolute_import  # Python 2 only

from typing import Text

from django.conf import settings
from django.template import TemplateSyntaxError

from zerver.templatetags.minified_js import MinifiedJSNode


def minified_js(sourcefile):
    # type: (str) -> Text
    if sourcefile not in settings.JS_SPECS:
        raise TemplateSyntaxError(
            "Invalid argument: no JS file %s".format(sourcefile))

    return MinifiedJSNode(sourcefile).render({})
