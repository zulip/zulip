from typing import Any, Dict, List, Optional

import markdown
import markdown.extensions.admonition
import markdown.extensions.codehilite
import markdown.extensions.extra
import markdown.extensions.toc
from django.template import Library, engines
from django.utils.safestring import mark_safe
from jinja2.exceptions import TemplateNotFound

import zerver.lib.bugdown.fenced_code
import zerver.lib.bugdown.api_arguments_table_generator
import zerver.lib.bugdown.api_code_examples
import zerver.lib.bugdown.nested_code_blocks
import zerver.lib.bugdown.tabbed_sections
import zerver.lib.bugdown.help_settings_links
import zerver.lib.bugdown.help_relative_links
import zerver.lib.bugdown.help_emoticon_translations_table
import zerver.lib.bugdown.include
from zerver.lib.cache import ignore_unhashable_lru_cache, dict_to_items_tuple, items_tuple_to_dict

register = Library()

def and_n_others(values: List[str], limit: int) -> str:
    # A helper for the commonly appended "and N other(s)" string, with
    # the appropriate pluralization.
    return " and %d other%s" % (len(values) - limit,
                                "" if len(values) == limit + 1 else "s")

@register.filter(name='display_list', is_safe=True)
def display_list(values: List[str], display_limit: int) -> str:
    """
    Given a list of values, return a string nicely formatting those values,
    summarizing when you have more than `display_limit`. Eg, for a
    `display_limit` of 3 we get the following possible cases:

    Jessica
    Jessica and Waseem
    Jessica, Waseem, and Tim
    Jessica, Waseem, Tim, and 1 other
    Jessica, Waseem, Tim, and 2 others
    """
    if len(values) == 1:
        # One value, show it.
        display_string = "%s" % (values[0],)
    elif len(values) <= display_limit:
        # Fewer than `display_limit` values, show all of them.
        display_string = ", ".join(
            "%s" % (value,) for value in values[:-1])
        display_string += " and %s" % (values[-1],)
    else:
        # More than `display_limit` values, only mention a few.
        display_string = ", ".join(
            "%s" % (value,) for value in values[:display_limit])
        display_string += and_n_others(values, display_limit)

    return display_string

md_extensions = None  # type: Optional[List[Any]]
md_macro_extension = None  # type: Optional[Any]
# Prevent the automatic substitution of macros in these docs. If
# they contain a macro, it is always used literally for documenting
# the macro system.
docs_without_macros = [
    "incoming-webhooks-walkthrough.md",
]

# render_markdown_path is passed a context dictionary (unhashable), which
# results in the calls not being cached. To work around this, we convert the
# dict to a tuple of dict items to cache the results.
@dict_to_items_tuple
@ignore_unhashable_lru_cache(512)
@items_tuple_to_dict
@register.filter(name='render_markdown_path', is_safe=True)
def render_markdown_path(markdown_file_path: str,
                         context: Optional[Dict[Any, Any]]=None,
                         pure_markdown: Optional[bool]=False) -> str:
    """Given a path to a markdown file, return the rendered html.

    Note that this assumes that any HTML in the markdown file is
    trusted; it is intended to be used for documentation, not user
    data."""

    if context is None:
        context = {}

    # We set this global hackishly
    from zerver.lib.bugdown.help_settings_links import set_relative_settings_links
    set_relative_settings_links(bool(context.get('html_settings_links')))
    from zerver.lib.bugdown.help_relative_links import set_relative_help_links
    set_relative_help_links(bool(context.get('html_settings_links')))

    global md_extensions
    global md_macro_extension
    if md_extensions is None:
        md_extensions = [
            markdown.extensions.extra.makeExtension(),
            markdown.extensions.toc.makeExtension(),
            markdown.extensions.admonition.makeExtension(),
            markdown.extensions.codehilite.makeExtension(
                linenums=False,
                guess_lang=False
            ),
            zerver.lib.bugdown.fenced_code.makeExtension(
                run_content_validators=context.get('run_content_validators', False)
            ),
            zerver.lib.bugdown.api_arguments_table_generator.makeExtension(
                base_path='templates/zerver/api/'),
            zerver.lib.bugdown.nested_code_blocks.makeExtension(),
            zerver.lib.bugdown.tabbed_sections.makeExtension(),
            zerver.lib.bugdown.help_settings_links.makeExtension(),
            zerver.lib.bugdown.help_relative_links.makeExtension(),
            zerver.lib.bugdown.help_emoticon_translations_table.makeExtension(),
        ]
    if md_macro_extension is None:
        md_macro_extension = zerver.lib.bugdown.include.makeExtension(
            base_path='templates/zerver/help/include/')
    extensions = md_extensions
    if 'api_url' in context:
        # We need to generate the API code examples extension each
        # time so the `api_url` config parameter can be set dynamically.
        #
        # TODO: Convert this to something more efficient involving
        # passing the API URL as a direct parameter.
        extensions = extensions + [zerver.lib.bugdown.api_code_examples.makeExtension(
            api_url=context["api_url"],
        )]
    if not any(doc in markdown_file_path for doc in docs_without_macros):
        extensions = extensions + [md_macro_extension]

    md_engine = markdown.Markdown(extensions=extensions)
    md_engine.reset()

    jinja = engines['Jinja2']

    try:
        # By default, we do both Jinja2 templating and markdown
        # processing on the file, to make it easy to use both Jinja2
        # context variables and markdown includes in the file.
        markdown_string = jinja.env.loader.get_source(jinja.env, markdown_file_path)[0]
    except TemplateNotFound as e:
        if pure_markdown:
            # For files such as /etc/zulip/terms.md where we don't intend
            # to use Jinja2 template variables, we still try to load the
            # template using Jinja2 (in case the file path isn't absolute
            # and does happen to be in Jinja's recognized template
            # directories), and if that fails, we try to load it directly
            # from disk.
            with open(markdown_file_path) as fp:
                markdown_string = fp.read()
        else:
            raise e

    html = md_engine.convert(markdown_string)
    rendered_html = jinja.from_string(html).render(context)

    return mark_safe(rendered_html)

import json
import copy
def dump_example(data: Dict[str, Any]) -> str:
    newdata = copy.deepcopy(data)
    if 'event_description' in data:
        del newdata['event_description']
        del newdata['instrumented_event_id']
    return json.dumps(newdata, sort_keys=True, indent=4)
