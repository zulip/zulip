import re
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing import Any, Dict, Optional, List
import markdown

from zerver.openapi.openapi import get_openapi_description

MACRO_REGEXP = re.compile(r'\{generate_api_description(\(\s*(.+?)\s*\))}')

class APIDescriptionGenerator(Extension):
    def __init__(self, api_url: Optional[str]) -> None:
        self.config = {
            'api_url': [
                api_url,
                'API URL to use when rendering api links'
            ]
        }

    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'generate_api_description', APIDescriptionPreprocessor(md, self.getConfigs()), '_begin'
        )

class APIDescriptionPreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Dict[str, Any]) -> None:
        super().__init__(md)
        self.api_url = config['api_url']

    def run(self, lines: List[str]) -> List[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = MACRO_REGEXP.search(line)

                if match:
                    function = match.group(2)
                    text = self.render_description(function)
                    # The line that contains the directive to include the macro
                    # may be preceded or followed by text or tags, in that case
                    # we need to make sure that any preceding or following text
                    # stays the same.
                    line_split = MACRO_REGEXP.split(line, maxsplit=0)
                    preceding = line_split[0]
                    following = line_split[-1]
                    text = [preceding] + text + [following]
                    lines = lines[:loc] + text + lines[loc+1:]
                    break
            else:
                done = True
        return lines

    def render_description(self, function: str) -> List[str]:
        description: List[str] = []
        path, method = function.rsplit(':', 1)
        description_dict = get_openapi_description(path, method)
        description_dict = description_dict.replace('{{api_url}}', self.api_url)
        description.extend(description_dict.splitlines())
        return description

def makeExtension(*args: Any, **kwargs: str) -> APIDescriptionGenerator:
    return APIDescriptionGenerator(*args, **kwargs)
