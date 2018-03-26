"""
The contents of this file are taken from
https://github.com/niwinz/django-jinja/blob/master/django_jinja/management/commands/makemessages.py

Jinja2's i18n functionality is not exactly the same as Django's.
In particular, the tags names and their syntax are different:

  1. The Django ``trans`` tag is replaced by a _() global.
  2. The Django ``blocktrans`` tag is called ``trans``.

(1) isn't an issue, since the whole ``makemessages`` process is based on
converting the template tags to ``_()`` calls. However, (2) means that
those Jinja2 ``trans`` tags will not be picked up by Django's
``makemessages`` command.

There aren't any nice solutions here. While Jinja2's i18n extension does
come with extraction capabilities built in, the code behind ``makemessages``
unfortunately isn't extensible, so we can:

  * Duplicate the command + code behind it.
  * Offer a separate command for Jinja2 extraction.
  * Try to get Django to offer hooks into makemessages().
  * Monkey-patch.

We are currently doing that last thing. It turns out there we are lucky
for once: It's simply a matter of extending two regular expressions.
Credit for the approach goes to:
http://stackoverflow.com/questions/2090717

"""

import glob
import json
import os
import re
from argparse import ArgumentParser
from typing import Any, Dict, Iterable, List, Mapping, Text

from django.conf import settings
from django.core.management.commands import makemessages
from django.template.base import BLOCK_TAG_END, BLOCK_TAG_START
from django.utils.translation import template

from zerver.lib.str_utils import force_text

strip_whitespace_right = re.compile("(%s-?\\s*(trans|pluralize).*?-%s)\\s+" % (
                                    BLOCK_TAG_START, BLOCK_TAG_END), re.U)
strip_whitespace_left = re.compile("\\s+(%s-\\s*(endtrans|pluralize).*?-?%s)" % (
                                   BLOCK_TAG_START, BLOCK_TAG_END), re.U)

regexes = ['{{#tr .*?}}([\s\S]*?){{/tr}}',  # '.' doesn't match '\n' by default
           '{{\s*t "(.*?)"\W*}}',
           "{{\s*t '(.*?)'\W*}}",
           "i18n\.t\('([^\']*?)'\)",
           "i18n\.t\('(.*?)',\s*.*?[^,]\)",
           'i18n\.t\("([^\"]*?)"\)',
           'i18n\.t\("(.*?)",\s*.*?[^,]\)',
           ]
tags = [('err_', "error"),
        ]

frontend_compiled_regexes = [re.compile(regex) for regex in regexes]
multiline_js_comment = re.compile("/\*.*?\*/", re.DOTALL)
singleline_js_comment = re.compile("//.*?\n")

def strip_whitespaces(src: Text) -> Text:
    src = strip_whitespace_left.sub('\\1', src)
    src = strip_whitespace_right.sub('\\1', src)
    return src

class Command(makemessages.Command):

    xgettext_options = makemessages.Command.xgettext_options
    for func, tag in tags:
        xgettext_options += ['--keyword={}:1,"{}"'.format(func, tag)]

    def add_arguments(self, parser: ArgumentParser) -> None:
        super(Command, self).add_arguments(parser)
        parser.add_argument('--frontend-source', type=str,
                            default='static/templates',
                            help='Name of the Handlebars template directory')
        parser.add_argument('--frontend-output', type=str,
                            default='static/locale',
                            help='Name of the frontend messages output directory')
        parser.add_argument('--frontend-namespace', type=str,
                            default='translations.json',
                            help='Namespace of the frontend locale file')

    def handle(self, *args: Any, **options: Any) -> None:
        self.handle_django_locales(*args, **options)
        self.handle_frontend_locales(**options)

    def handle_frontend_locales(self, *,
                                frontend_source: str,
                                frontend_output: str,
                                frontend_namespace: str,
                                locale: List[str],
                                exclude: List[str],
                                all: bool,
                                **options: Any) -> None:
        self.frontend_source = frontend_source
        self.frontend_output = frontend_output
        self.frontend_namespace = frontend_namespace
        self.frontend_locale = locale
        self.frontend_exclude = exclude
        self.frontend_all = all

        translation_strings = self.get_translation_strings()
        self.write_translation_strings(translation_strings)

    def handle_django_locales(self, *args: Any, **options: Any) -> None:
        old_endblock_re = template.endblock_re
        old_block_re = template.block_re
        old_constant_re = template.constant_re

        old_templatize = template.templatize
        # Extend the regular expressions that are used to detect
        # translation blocks with an "OR jinja-syntax" clause.
        template.endblock_re = re.compile(
            template.endblock_re.pattern + '|' + r"""^-?\s*endtrans\s*-?$""")
        template.block_re = re.compile(
            template.block_re.pattern + '|' + r"""^-?\s*trans(?:\s+(?!'|")(?=.*?=.*?)|\s*-?$)""")
        template.plural_re = re.compile(
            template.plural_re.pattern + '|' + r"""^-?\s*pluralize(?:\s+.+|-?$)""")
        template.constant_re = re.compile(r"""_\(((?:".*?")|(?:'.*?')).*\)""")

        def my_templatize(src: Text, *args: Any, **kwargs: Any) -> Text:
            new_src = strip_whitespaces(src)
            return old_templatize(new_src, *args, **kwargs)

        template.templatize = my_templatize

        try:
            ignore_patterns = options.get('ignore_patterns', [])
            ignore_patterns.append('docs/*')
            ignore_patterns.append('var/*')
            options['ignore_patterns'] = ignore_patterns
            super().handle(*args, **options)
        finally:
            template.endblock_re = old_endblock_re
            template.block_re = old_block_re
            template.templatize = old_templatize
            template.constant_re = old_constant_re

    def extract_strings(self, data: str) -> List[str]:
        translation_strings = []  # type: List[str]
        for regex in frontend_compiled_regexes:
            for match in regex.findall(data):
                match = match.strip()
                match = ' '.join(line.strip() for line in match.splitlines())
                match = match.replace('\n', '\\n')
                translation_strings.append(match)

        return translation_strings

    def ignore_javascript_comments(self, data: str) -> str:
        # Removes multi line comments.
        data = multiline_js_comment.sub('', data)
        # Removes single line (//) comments.
        data = singleline_js_comment.sub('', data)
        return data

    def get_translation_strings(self) -> List[str]:
        translation_strings = []  # type: List[str]
        dirname = self.get_template_dir()

        for dirpath, dirnames, filenames in os.walk(dirname):
            for filename in [f for f in filenames if f.endswith(".handlebars")]:
                if filename.startswith('.'):
                    continue
                with open(os.path.join(dirpath, filename), 'r') as reader:
                    data = reader.read()
                    translation_strings.extend(self.extract_strings(data))

        dirname = os.path.join(settings.DEPLOY_ROOT, 'static/js')
        for filename in os.listdir(dirname):
            if filename.endswith('.js') and not filename.startswith('.'):
                with open(os.path.join(dirname, filename)) as reader:
                    data = reader.read()
                    data = self.ignore_javascript_comments(data)
                    translation_strings.extend(self.extract_strings(data))

        return list(set(translation_strings))

    def get_template_dir(self) -> str:
        return self.frontend_source

    def get_namespace(self) -> str:
        return self.frontend_namespace

    def get_locales(self) -> Iterable[str]:
        locale = self.frontend_locale
        exclude = self.frontend_exclude
        process_all = self.frontend_all

        paths = glob.glob('%s/*' % self.default_locale_path,)
        all_locales = [os.path.basename(path) for path in paths if os.path.isdir(path)]

        # Account for excluded locales
        if process_all:
            return all_locales
        else:
            locales = locale or all_locales
            return set(locales) - set(exclude)

    def get_base_path(self) -> str:
        return self.frontend_output

    def get_output_paths(self) -> Iterable[str]:
        base_path = self.get_base_path()
        locales = self.get_locales()
        for path in [os.path.join(base_path, locale) for locale in locales]:
            if not os.path.exists(path):
                os.makedirs(path)

            yield os.path.join(path, self.get_namespace())

    def get_new_strings(self, old_strings: Mapping[str, str],
                        translation_strings: List[str], locale: str) -> Dict[str, str]:
        """
        Missing strings are removed, new strings are added and already
        translated strings are not touched.
        """
        new_strings = {}  # Dict[str, str]
        for k in translation_strings:
            k = k.replace('\\n', '\n')
            if locale == 'en':
                # For English language, translation is equal to the key.
                new_strings[k] = old_strings.get(k, k)
            else:
                new_strings[k] = old_strings.get(k, "")

        plurals = {k: v for k, v in old_strings.items() if k.endswith('_plural')}
        for plural_key, value in plurals.items():
            components = plural_key.split('_')
            singular_key = '_'.join(components[:-1])
            if singular_key in new_strings:
                new_strings[plural_key] = value

        return new_strings

    def write_translation_strings(self, translation_strings: List[str]) -> None:
        for locale, output_path in zip(self.get_locales(), self.get_output_paths()):
            self.stdout.write("[frontend] processing locale {}".format(locale))
            try:
                with open(output_path, 'r') as reader:
                    old_strings = json.load(reader)
            except (IOError, ValueError):
                old_strings = {}

            new_strings = {
                force_text(k): v
                for k, v in self.get_new_strings(old_strings,
                                                 translation_strings,
                                                 locale).items()
            }
            with open(output_path, 'w') as writer:
                json.dump(new_strings, writer, indent=2, sort_keys=True)
