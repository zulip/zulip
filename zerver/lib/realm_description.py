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
    if not description:
        return ("", markdown_version)

    rendered_description = markdown_convert(
        description,
        message_realm=realm,
        no_previews=True,
    ).rendered_content

    return (rendered_description, markdown_version)


@cache_with_key(realm_rendered_description_cache_key, timeout=3600 * 24 * 7)
def get_realm_rendered_description(realm: Realm) -> str:
    if (
        realm.rendered_description is None
        or realm.rendered_description_version is None
        or realm.rendered_description_version < markdown_version
    ):
        rendered_description, version = render_realm_description(realm.description, realm)
        realm.rendered_description = rendered_description
        realm.rendered_description_version = version
        realm.save(update_fields=["rendered_description", "rendered_description_version"])

    if realm.rendered_description == "":
        return "<p>The coolest place in the universe.</p>"
    return realm.rendered_description


@cache_with_key(realm_text_description_cache_key, timeout=3600 * 24 * 7)
def get_realm_text_description(realm: Realm) -> str:
    html_description = get_realm_rendered_description(realm)
    return html_to_text(html_description, {"p": " | ", "li": " * "})
