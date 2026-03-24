import markdownify


def convert_html_to_markdown(html: str) -> str:
    # Use ATX-style headings (e.g. "# Title") since Zulip's Markdown
    # renderer does not support Setext-style underline headings.
    return markdownify.markdownify(html, heading_style="ATX").strip()
