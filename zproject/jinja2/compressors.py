"""
`minified_js` is taken from `zerver.templatetags.minified_js.py`
"""
from __future__ import absolute_import  # Python 2 only

from django.conf import settings
from django.template import TemplateSyntaxError
from pipeline.templatetags.compressed import CompressedCSSNode

from zerver.templatetags.minified_js import MinifiedJSNode


def compressed_css(package_name):
    return CompressedCSSNode(package_name).render({package_name: package_name})


def minified_js(sourcefile):
    if sourcefile not in settings.JS_SPECS:
        raise TemplateSyntaxError(
            "Invalid argument: no JS file %s".format(sourcefile))

    return MinifiedJSNode(sourcefile).render({})
