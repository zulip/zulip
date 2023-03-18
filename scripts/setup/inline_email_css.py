#!/usr/bin/env python3
import os
import re
from typing import List, Set

import css_inline
from polib import POEntry

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")
EMAIL_TEMPLATES_PATH = os.path.join(ZULIP_PATH, "templates", "zerver", "emails")
CSS_SOURCE_PATH = os.path.join(EMAIL_TEMPLATES_PATH, "email.css")


def get_inliner_instance() -> css_inline.CSSInliner:
    with open(CSS_SOURCE_PATH) as file:
        content = file.read()
    return css_inline.CSSInliner(extra_css=content)


inliner = get_inliner_instance()


def remove_unnecessary_tags(str: str) -> str:
    output = escape_jinja2_characters(str)
    output = strip_unnecessary_tags(output)

    return re.sub(r"{% extends|\</p>", "", output)


def get_css_inlined_list(poentry_list: List[POEntry]) -> List[POEntry]:
    css_inlined_poentry_list: List[POEntry] = []
    start_block = "{% extends"

    for entry in poentry_list:
        css_inlined_msgid = remove_unnecessary_tags(inliner.inline(start_block + entry.msgid))
        css_inlined_msgstr = remove_unnecessary_tags(inliner.inline(start_block + entry.msgstr))

        if css_inlined_msgid.strip() == entry.msgid.strip():
            # Some tags, like <b>, may not actually have any CSS, so
            # some strings passed to this function may be unchanged.
            continue

        css_inlined_poentry_list.append(
            POEntry(
                msgid=css_inlined_msgid,
                msgstr=css_inlined_msgstr,
            )
        )

    return css_inlined_poentry_list


def inline_template(template_source_name: str) -> None:
    template_name = template_source_name.split(".source.html")[0]
    template_path = os.path.join(EMAIL_TEMPLATES_PATH, template_source_name)
    compiled_template_path = os.path.join(
        os.path.dirname(template_path), "compiled", os.path.basename(template_name) + ".html"
    )

    os.makedirs(os.path.dirname(compiled_template_path), exist_ok=True)

    with open(template_path) as template_source_file:
        template_str = template_source_file.read()
    output = inliner.inline(template_str)

    output = escape_jinja2_characters(output)

    # Inline method of css-inline will try to complete the DOM tree,
    # adding html, head, and body tags if they aren't there.
    # While this is correct for the email_base_default template,
    # it is wrong for the other templates that extend this
    # template, since we'll end up with 2 copies of those tags.
    # Thus, we strip this stuff out if the template extends
    # another template.
    if template_name not in ["email_base_default", "email_base_marketing", "macros"]:
        output = strip_unnecessary_tags(output)

    if (
        "zerver/emails/compiled/email_base_default.html" in output
        or "zerver/emails/compiled/email_base_marketing.html" in output
        or "zerver/emails/email_base_messages.html" in output
    ):
        assert output.count("<html>") == 0
        assert output.count("<body>") == 0
        assert output.count("</html>") == 0
        assert output.count("</body>") == 0

    with open(compiled_template_path, "w") as final_template_file:
        final_template_file.write(output)


def escape_jinja2_characters(text: str) -> str:
    escaped_jinja2_characters = [("%7B%7B%20", "{{ "), ("%20%7D%7D", " }}"), ("&gt;", ">")]
    for escaped, original in escaped_jinja2_characters:
        text = text.replace(escaped, original)
    return text


def strip_unnecessary_tags(text: str) -> str:
    end_block = "</body></html>"
    start_block = "{% extends"
    start = text.find(start_block)
    end = text.rfind(end_block)
    if start != -1 and end != -1:
        text = text[start:end]
        return text
    else:
        raise ValueError(f"Template does not have {start_block} or {end_block}")


def get_all_templates_from_directory(directory: str) -> Set[str]:
    result = set()
    for f in os.listdir(directory):
        if f.endswith(".source.html"):
            result.add(f)
    return result


if __name__ == "__main__":
    templates_to_inline = get_all_templates_from_directory(EMAIL_TEMPLATES_PATH)

    for template_source_name in templates_to_inline:
        inline_template(template_source_name)
