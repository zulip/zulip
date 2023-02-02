import time
from typing import Any, Dict, List, Optional

import markdown
import markdown.extensions.admonition
import markdown.extensions.codehilite
import markdown.extensions.extra
import markdown.extensions.toc
import orjson
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template import Library, engines
from django.template.backends.jinja2 import Jinja2
from django.utils.safestring import mark_safe
from jinja2.exceptions import TemplateNotFound

import zerver.lib.markdown.api_arguments_table_generator
import zerver.lib.markdown.api_return_values_table_generator
import zerver.lib.markdown.fenced_code
import zerver.lib.markdown.help_emoticon_translations_table
import zerver.lib.markdown.help_relative_links
import zerver.lib.markdown.help_settings_links
import zerver.lib.markdown.include
import zerver.lib.markdown.nested_code_blocks
import zerver.lib.markdown.tabbed_sections
import zerver.openapi.markdown_extension
from zerver.lib.cache import dict_to_items_tuple, ignore_unhashable_lru_cache, items_tuple_to_dict

register = Library()


def and_n_others(values: List[str], limit: int) -> str:
    # A helper for the commonly appended "and N other(s)" string, with
    # the appropriate pluralization.
    return " and {} other{}".format(
        len(values) - limit,
        "" if len(values) == limit + 1 else "s",
    )


@register.filter(name="display_list", is_safe=True)
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
        display_string = f"{values[0]}"
    elif len(values) <= display_limit:
        # Fewer than `display_limit` values, show all of them.
        display_string = ", ".join(f"{value}" for value in values[:-1])
        display_string += f" and {values[-1]}"
    else:
        # More than `display_limit` values, only mention a few.
        display_string = ", ".join(f"{value}" for value in values[:display_limit])
        display_string += and_n_others(values, display_limit)

    return display_string


md_extensions: Optional[List[markdown.Extension]] = None
md_macro_extension: Optional[markdown.Extension] = None
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
@register.filter(name="render_markdown_path", is_safe=True)
def render_markdown_path(
    markdown_file_path: str, context: Optional[Dict[str, Any]] = None, pure_markdown: bool = False
) -> str:
    """Given a path to a Markdown file, return the rendered HTML.

    Note that this assumes that any HTML in the Markdown file is
    trusted; it is intended to be used for documentation, not user
    data."""
    if context is None:
        context = {}

    # We set this global hackishly
    from zerver.lib.markdown.help_settings_links import set_relative_settings_links

    set_relative_settings_links(bool(context.get("html_settings_links")))
    from zerver.lib.markdown.help_relative_links import set_relative_help_links

    set_relative_help_links(bool(context.get("html_settings_links")))

    global md_extensions
    global md_macro_extension
    if md_extensions is None:
        md_extensions = [
            markdown.extensions.extra.makeExtension(),
            markdown.extensions.toc.makeExtension(),
            markdown.extensions.admonition.makeExtension(),
            markdown.extensions.codehilite.makeExtension(
                linenums=False,
                guess_lang=False,
            ),
            zerver.lib.markdown.fenced_code.makeExtension(
                run_content_validators=context.get("run_content_validators", False),
            ),
            zerver.lib.markdown.api_arguments_table_generator.makeExtension(
                base_path="templates/zerver/api/"
            ),
            zerver.lib.markdown.api_return_values_table_generator.makeExtension(
                base_path="templates/zerver/api/"
            ),
            zerver.lib.markdown.nested_code_blocks.makeExtension(),
            zerver.lib.markdown.tabbed_sections.makeExtension(),
            zerver.lib.markdown.help_settings_links.makeExtension(),
            zerver.lib.markdown.help_relative_links.makeExtension(),
            zerver.lib.markdown.help_emoticon_translations_table.makeExtension(),
        ]
    if md_macro_extension is None:
        md_macro_extension = zerver.lib.markdown.include.makeExtension(
            base_path="templates/zerver/help/include/"
        )
    if "api_url" in context:
        # We need to generate the API code examples extension each
        # time so the `api_url` config parameter can be set dynamically.
        #
        # TODO: Convert this to something more efficient involving
        # passing the API URL as a direct parameter.
        extensions = [
            zerver.openapi.markdown_extension.makeExtension(
                api_url=context["api_url"],
            ),
            *md_extensions,
        ]
    else:
        extensions = md_extensions

    if not any(doc in markdown_file_path for doc in docs_without_macros):
        extensions = [md_macro_extension, *extensions]

    md_engine = markdown.Markdown(extensions=extensions)
    md_engine.reset()

    jinja = engines["Jinja2"]
    try:
        # By default, we do both Jinja2 templating and Markdown
        # processing on the file, to make it easy to use both Jinja2
        # context variables and markdown includes in the file.
        assert isinstance(jinja, Jinja2)
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

    API_ENDPOINT_NAME = context.get("API_ENDPOINT_NAME", "")
    markdown_string = markdown_string.replace("API_ENDPOINT_NAME", API_ENDPOINT_NAME)
    html = md_engine.convert(markdown_string)
    rendered_html = jinja.from_string(html).render(context)

    return mark_safe(rendered_html)


def webpack_entry(entrypoint: str) -> List[str]:
    while True:
        with open(settings.WEBPACK_STATS_FILE, "rb") as f:
            stats = orjson.loads(f.read())
        status = stats["status"]
        if not settings.DEBUG or status != "compile":
            break
        time.sleep(0.2)

    if status != "done":
        raise RuntimeError("Webpack compilation was not successful")

    try:
        files_from_entrypoints = [
            staticfiles_storage.url(settings.WEBPACK_BUNDLES + filename)
            for filename in stats["chunks"][entrypoint]
            if filename.endswith((".css", ".js")) and not filename.endswith(".hot-update.js")
        ]
    except KeyError:
        raise KeyError(
            f"'{entrypoint}' entrypoint could not be found. Please define it in tools/webpack.assets.json."
        )

    return files_from_entrypoints
