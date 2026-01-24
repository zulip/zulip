from zerver.lib.markdown import markdown_convert
from zerver.lib.markdown import version as markdown_version
from zerver.models import Realm


def render_user_group_description(description: str, realm: Realm) -> tuple[str, int]:
    """Render user group description to HTML. Returns (rendered_html, version)."""
    if not description:
        return ("", markdown_version)
    rendered = markdown_convert(
        description,
        message_realm=realm,
        no_previews=True,
    ).rendered_content
    return (rendered, markdown_version)
