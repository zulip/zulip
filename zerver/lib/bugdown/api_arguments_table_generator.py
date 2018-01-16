import re
import os
import ujson

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing import Any, Dict, Optional, List
import markdown

REGEXP = re.compile(r'\{generate_api_arguments_table\|\s*(.+?)\s*\|\s*(.+?)\s*\}')


class MarkdownArgumentsTableGenerator(Extension):
    def __init__(self, configs: Optional[Dict[str, Any]]={}) -> None:
        self.config = {
            'base_path': ['.', 'Default location from which to evaluate relative paths for the JSON files.'],
        }
        for key, value in configs.items():
            self.setConfig(key, value)

    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'generate_api_arguments', APIArgumentsTablePreprocessor(md, self.getConfigs()), '_begin'
        )


class APIArgumentsTablePreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Dict[str, Any]) -> None:
        super(APIArgumentsTablePreprocessor, self).__init__(md)
        self.base_path = config['base_path']

    def run(self, lines: List[str]) -> List[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = REGEXP.search(line)

                if match:
                    json_filename = match.group(1)
                    doc_filename = match.group(2)
                    json_filename = os.path.expanduser(json_filename)
                    if not os.path.isabs(json_filename):
                        json_filename = os.path.normpath(os.path.join(self.base_path, json_filename))
                    try:
                        with open(json_filename, 'r') as fp:
                            json_obj = ujson.loads(fp.read())
                            arguments = json_obj[doc_filename]
                            text = self.render_table(arguments)
                    except Exception as e:
                        print('Warning: could not find file {}. Ignoring '
                              'statement. Error: {}'.format(json_filename, e))
                        # If the file cannot be opened, just substitute an empty line
                        # in place of the macro include line
                        lines[loc] = REGEXP.sub('', line)
                        break

                    # The line that contains the directive to include the macro
                    # may be preceded or followed by text or tags, in that case
                    # we need to make sure that any preceding or following text
                    # stays the same.
                    line_split = REGEXP.split(line, maxsplit=0)
                    preceding = line_split[0]
                    following = line_split[-1]
                    text = [preceding] + text + [following]
                    lines = lines[:loc] + text + lines[loc+1:]
                    break
            else:
                done = True
        return lines

    def render_table(self, arguments: List[Dict[str, Any]]) -> List[str]:
        table = []
        beginning = """
<table class="table">
  <thead>
    <tr>
      <th>Argument</th>
      <th>Example</th>
      <th>Required</th>
      <th>Description</th>
    </tr>
  </thead>
<tbody>
"""
        tr = """
<tr>
  <td><code>{argument}</code></td>
  <td><code>{example}</code></td>
  <td>{required}</td>
  <td>{description}</td>
</tr>
"""

        table.append(beginning)

        md_engine = markdown.Markdown(extensions=[])

        for argument in arguments:
            table.append(tr.format(
                argument=argument['argument'],
                example=argument['example'],
                required=argument['required'],
                description=md_engine.convert(argument['description']),
            ))

        table.append("</tbody>")
        table.append("</table>")

        return table

def makeExtension(*args: Any, **kwargs: str) -> MarkdownArgumentsTableGenerator:
    return MarkdownArgumentsTableGenerator(kwargs)
