import json
import os
import re
from typing import Any, Dict, List, Mapping, Sequence

import markdown
from django.utils.html import escape as escape_html
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from zerver.openapi.openapi import get_openapi_parameters, likely_deprecated_parameter

REGEXP = re.compile(r'\{generate_api_arguments_table\|\s*(.+?)\s*\|\s*(.+)\s*\}')


class MarkdownArgumentsTableGenerator(Extension):
    def __init__(self, configs: Mapping[str, Any] = {}) -> None:
        self.config = {
            'base_path': ['.', 'Default location from which to evaluate relative paths for the JSON files.'],
        }
        for key, value in configs.items():
            self.setConfig(key, value)

    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'generate_api_arguments', APIArgumentsTablePreprocessor(md, self.getConfigs()), '_begin',
        )


class APIArgumentsTablePreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Dict[str, Any]) -> None:
        super().__init__(md)
        self.base_path = config['base_path']

    def run(self, lines: List[str]) -> List[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = REGEXP.search(line)

                if not match:
                    continue

                filename = match.group(1)
                doc_name = match.group(2)
                filename = os.path.expanduser(filename)

                is_openapi_format = filename.endswith('.yaml')

                if not os.path.isabs(filename):
                    parent_dir = self.base_path
                    filename = os.path.normpath(os.path.join(parent_dir, filename))

                if is_openapi_format:
                    endpoint, method = doc_name.rsplit(':', 1)
                    arguments: List[Dict[str, Any]] = []

                    try:
                        arguments = get_openapi_parameters(endpoint, method)
                    except KeyError as e:
                        # Don't raise an exception if the "parameters"
                        # field is missing; we assume that's because the
                        # endpoint doesn't accept any parameters
                        if e.args != ('parameters',):
                            raise e
                else:
                    with open(filename) as fp:
                        json_obj = json.load(fp)
                        arguments = json_obj[doc_name]

                if arguments:
                    text = self.render_table(arguments)
                else:
                    text = ['This endpoint does not accept any parameters.']
                # The line that contains the directive to include the macro
                # may be preceded or followed by text or tags, in that case
                # we need to make sure that any preceding or following text
                # stays the same.
                line_split = REGEXP.split(line, maxsplit=0)
                preceding = line_split[0]
                following = line_split[-1]
                text = [preceding, *text, following]
                lines = lines[:loc] + text + lines[loc+1:]
                break
            else:
                done = True
        return lines

    def render_table(self, arguments: Sequence[Mapping[str, Any]]) -> List[str]:
        # TODO: Fix naming now that this no longer renders a table.
        table = []
        argument_template = """
<div class="api-argument">
    <p class="api-argument-name"><strong>{argument}</strong> {required} {deprecated}</p>
    <div class="api-example">
        <span class="api-argument-example-label">Example</span>: <code>{example}</code>
    </div>
    <div class="api-description">{description}</div>
    <hr>
</div>"""

        md_engine = markdown.Markdown(extensions=[])
        arguments = sorted(arguments, key=lambda argument: 'deprecated' in argument)
        for argument in arguments:
            description = argument['description']
            oneof = ['`' + str(item) + '`'
                     for item in argument.get('schema', {}).get('enum', [])]
            if oneof:
                description += '\nMust be one of: {}.'.format(', '.join(oneof))

            default = argument.get('schema', {}).get('default')
            if default is not None:
                description += f'\nDefaults to `{json.dumps(default)}`.'

            # TODO: OpenAPI allows indicating where the argument goes
            # (path, querystring, form data...).  We should document this detail.
            example = ""
            if 'example' in argument:
                example = argument['example']
            else:
                example = json.dumps(argument['content']['application/json']['example'])

            required_string: str = "required"
            if argument.get('in', '') == 'path':
                # Any path variable is required
                assert argument['required']
                required_string = 'required in path'

            if argument.get('required', False):
                required_block = f'<span class="api-argument-required">{required_string}</span>'
            else:
                required_block = '<span class="api-argument-optional">optional</span>'

            # Test to make sure deprecated parameters are marked so.
            if likely_deprecated_parameter(description):
                assert(argument['deprecated'])
            if argument.get('deprecated', False):
                deprecated_block = '<span class="api-argument-deprecated">Deprecated</span>'
            else:
                deprecated_block = ''

            table.append(argument_template.format(
                argument=argument.get('argument') or argument.get('name'),
                example=escape_html(example),
                required=required_block,
                deprecated=deprecated_block,
                description=md_engine.convert(description),
            ))

        return table

def makeExtension(*args: Any, **kwargs: str) -> MarkdownArgumentsTableGenerator:
    return MarkdownArgumentsTableGenerator(kwargs)
