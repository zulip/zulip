from zerver.lib.cache import (
    cache_with_key,
    realm_rendered_description_cache_key,
    realm_text_description_cache_key,
)
from zerver.lib.html_to_text import html_to_text
from zerver.lib.markdown import markdown_convert
from zerver.lib.markdown import version as markdown_version
from zerver.models import Realm


def render_realm_description(description: str, realm: Realm | None = None) -> tuple[str, int]:
    """Render description to HTML. Returns (rendered_html, version)."""
    if not description:
        return ("", markdown_version)

    rendered = markdown_convert(
        description,
        message_realm=realm,
        no_previews=True,
    ).rendered_content

    return (rendered, markdown_version)


@cache_with_key(realm_rendered_description_cache_key, timeout=3600 * 24 * 7)
def get_realm_rendered_description(realm: Realm) -> str:
    if (
        realm.rendered_description is not None
        and realm.rendered_description_version is not None
        and realm.rendered_description_version >= markdown_version
    ):
        if realm.rendered_description == "":
            return "<p>The coolest place in the universe.</p>"
        return realm.rendered_description

    rendered_content, version = render_realm_description(realm.description, realm)
    realm.rendered_description = rendered_content
    realm.rendered_description_version = version
    realm.save(update_fields=["rendered_description", "rendered_description_version"])

    if rendered_content == "":
        return "<p>The coolest place in the universe.</p>"
    return rendered_content


@cache_with_key(realm_text_description_cache_key, timeout=3600 * 24 * 7)
def get_realm_text_description(realm: Realm) -> str:
    html_description = get_realm_rendered_description(realm)
    return html_to_text(html_description, {"p": " | ", "li": " * "})
