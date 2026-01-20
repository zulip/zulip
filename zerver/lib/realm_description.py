from zerver.lib.cache import (
    cache_with_key,
    realm_rendered_description_cache_key,
    realm_text_description_cache_key,
)
from zerver.lib.html_to_text import html_to_text
from zerver.lib.markdown import markdown_convert
from zerver.models import Realm


def render_realm_description(description: str, realm: Realm | None = None) -> str:
    # Use default if description is empty, otherwise use provided description
    description_to_render = description or "The coolest place in the universe."
    return markdown_convert(
        description_to_render,
        message_realm=realm,
        no_previews=True,
    ).rendered_content


@cache_with_key(realm_rendered_description_cache_key, timeout=3600 * 24 * 7)
def get_realm_rendered_description(realm: Realm) -> str:
    if realm.rendered_description is not None:
        return realm.rendered_description

    rendered_content = render_realm_description(realm.description, realm)
    realm.rendered_description = rendered_content
    realm.save(update_fields=["rendered_description"])

    return rendered_content


@cache_with_key(realm_text_description_cache_key, timeout=3600 * 24 * 7)
def get_realm_text_description(realm: Realm) -> str:
    html_description = get_realm_rendered_description(realm)
    return html_to_text(html_description, {"p": " | ", "li": " * "})
