from __future__ import absolute_import

from django.template import Node, Library, TemplateSyntaxError
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

register = Library()

class MinifiedJSNode(Node):
    def __init__(self, sourcefile):
        self.sourcefile = sourcefile

    def render(self, context):
        if settings.DEBUG:
            scripts = settings.JS_SPECS[self.sourcefile]['source_filenames']
        else:
            scripts = [settings.JS_SPECS[self.sourcefile]['output_filename']]
        script_urls = [staticfiles_storage.url(script) for script in scripts]
        script_tags = ['<script type="text/javascript" src="%s" charset="utf-8"></script>'
                % url for url in script_urls]
        return '\n'.join(script_tags)


@register.tag
def minified_js(parser, token):
    try:
        tag_name, sourcefile = token.split_contents()
    except ValueError:
        raise TemplateSyntaxError("%s tag requires an argument" % (tag_name,))
    if not (sourcefile[0] == sourcefile[-1] and sourcefile[0] in ('"', "'")):
        raise TemplateSyntaxError("%s tag should be quoted" % (tag_name,))

    sourcefile = sourcefile[1:-1]
    if sourcefile not in settings.JS_SPECS:
        raise TemplateSyntaxError("%s tag invalid argument: no JS file %s"
                % (tag_name, sourcefile))
    return MinifiedJSNode(sourcefile)
