import re
from re import Match
from typing import Any

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing_extensions import override

from zerver.lib.emoji import EMOTICON_CONVERSIONS, name_to_codepoint
from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES

REGEXP = re.compile(r"\{emoticon_translations\}")

TABLE_HTML = """\
<table>
    <thead>
        <tr>
            <th>Emoticon</th>
            <th>Emoji</th>
        </tr>
    </thead>
    <tbody>
        {body}
    </tbody>
</table>
"""

ROW_HTML = """\
<tr>
    <td><code>{emoticon}</code></td>
    <td>
        <img
            src="/static/generated/emoji/images-google-64/{codepoint}.png"
            alt="{name}"
            class="emoji-big">
    </td>
</tr>
"""


class EmoticonTranslationsHelpExtension(Extension):
    @override
    def extendMarkdown(self, md: Markdown) -> None:
        """Add SettingHelpExtension to the Markdown instance."""
        md.registerExtension(self)
        md.preprocessors.register(
            EmoticonTranslation(),
            "emoticon_translations",
            PREPROCESSOR_PRIORITIES["emoticon_translations"],
        )


class EmoticonTranslation(Preprocessor):
    @override
    def run(self, lines: list[str]) -> list[str]:
        for loc, line in enumerate(lines):
            match = REGEXP.search(line)
            if match:
                text = self.handleMatch(match)
                lines = lines[:loc] + text + lines[loc + 1 :]
                break
        return lines

    def handleMatch(self, match: Match[str]) -> list[str]:
        rows = [
            ROW_HTML.format(
                emoticon=emoticon,
                name=name.strip(":"),
                codepoint=name_to_codepoint[name.strip(":")],
            )
            for emoticon, name in EMOTICON_CONVERSIONS.items()
        ]
        body = "".join(rows).strip()
        return TABLE_HTML.format(body=body).strip().splitlines()


def makeExtension(*args: Any, **kwargs: Any) -> EmoticonTranslationsHelpExtension:
    return EmoticonTranslationsHelpExtension(*args, **kwargs)
