import re
from typing import Any, Dict, List, Mapping, Optional

import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from zerver.openapi.openapi import get_openapi_return_values, likely_deprecated_parameter

REGEXP = re.compile(r'\{generate_return_values_table\|\s*(.+?)\s*\|\s*(.+)\s*\}')


class MarkdownReturnValuesTableGenerator(Extension):
    def __init__(self, configs: Mapping[str, Any] = {}) -> None:
        self.config: Dict[str, Any] = {}

    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'generate_return_values', APIReturnValuesTablePreprocessor(md, self.getConfigs()), '_begin',
        )


class APIReturnValuesTablePreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Dict[str, Any]) -> None:
        super().__init__(md)

    def run(self, lines: List[str]) -> List[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = REGEXP.search(line)

                if not match:
                    continue

                doc_name = match.group(2)
                endpoint, method = doc_name.rsplit(':', 1)
                return_values: Dict[str, Any] = {}
                return_values = get_openapi_return_values(endpoint, method)
                text = self.render_table(return_values, 0)
                line_split = REGEXP.split(line, maxsplit=0)
                preceding = line_split[0]
                following = line_split[-1]
                text = [preceding] + text + [following]
                lines = lines[:loc] + text + lines[loc+1:]
                break
            else:
                done = True
        return lines

    def render_desc(self, description: str, spacing: int, return_value: Optional[str]=None) -> str:
        description = description.replace('\n', '\n' + ((spacing + 4) * ' '))
        if return_value is None:
            return (spacing * " ") + "* " + description
        return (spacing * " ") + "* `" + return_value + "`: " + description

    def render_table(self, return_values: Dict[str, Any], spacing: int) -> List[str]:
        IGNORE = ["result", "msg"]
        ans = []
        for return_value in return_values:
            if return_value in IGNORE:
                continue
            description = return_values[return_value]['description']
            # Test to make sure deprecated keys are marked appropriately.
            if likely_deprecated_parameter(description):
                assert(return_values[return_value]['deprecated'])
            ans.append(self.render_desc(description, spacing, return_value))
            if 'properties' in return_values[return_value]:
                ans += self.render_table(return_values[return_value]['properties'], spacing + 4)
            if return_values[return_value].get('additionalProperties', False):
                ans.append(self.render_desc(return_values[return_value]['additionalProperties']
                                            ['description'], spacing + 4))
                if 'properties' in return_values[return_value]['additionalProperties']:
                    ans += self.render_table(return_values[return_value]['additionalProperties']
                                             ['properties'], spacing + 8)
            if ('items' in return_values[return_value] and
                    'properties' in return_values[return_value]['items']):
                ans += self.render_table(return_values[return_value]['items']['properties'], spacing + 4)
        return ans

def makeExtension(*args: Any, **kwargs: str) -> MarkdownReturnValuesTableGenerator:
    return MarkdownReturnValuesTableGenerator(kwargs)
