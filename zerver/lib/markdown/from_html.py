import posixpath
import re
import sys
import warnings
from urllib.parse import urlsplit

import markdownify
from bs4 import BeautifulSoup, Comment, MarkupResemblesLocatorWarning, Tag
from typing_extensions import override

from zerver.lib.markdown import get_markdown_link_for_url, sanitize_url


def is_data_table(table: Tag) -> bool:
    """Whether the table has a row of column headers, and converts to a
    valid Markdown table that keeps all of its content.

    Page layout tables also use <th>, for a banner spanning the table or
    for a cell that wraps a whole column of content, so require at least
    two header cells with no tables inside them.

    The remaining conditions are what a valid Markdown table needs:

    * Apart from a <colgroup> of <col> elements before its rows, the
      table holds only <thead> and <tbody> sections, rows of cells, and
      what is inside the cells. markdownify converts other content to
      text between the rows, and a stray row, section or cell inside a
      cell to a row or cell.
    * No text, link or image contains "|", which markdownify doesn't
      escape.
    * The table isn't inside a link, or inside a stray cell that has no
      table around it, as neither can hold a table.
    * markdownify's convert_tr converts a row to the header row only when
      it is the first element of its section and is all <th> or the only
      row of a <thead>. It also starts another header at the first row of
      each later section, except for a <tbody> after a <thead> that
      doesn't start with a row of <th>.
    * Every row has cells, and no more columns than the header row, as
      Zulip's Markdown drops a row's cells beyond that. Columns can only
      be counted when each colspan is a number of at most four digits,
      which covers every value that HTML allows.
    """

    def has_only_children(parent: Tag, names: list[str]) -> bool:
        for child in parent.children:
            if isinstance(child, Tag):
                if child.name not in names:
                    return False
            elif not isinstance(child, Comment) and str(child).strip():
                return False
        return True

    def get_cells(row: Tag) -> list[Tag]:
        return row.find_all(["th", "td"], recursive=False)

    def is_all_th(row: Tag) -> bool:
        return all(cell.name == "th" for cell in get_cells(row))

    def get_column_count(row: Tag) -> int | None:
        column_count = 0
        for cell in get_cells(row):
            colspan = cell.get("colspan", "1")
            if not isinstance(colspan, str) or not colspan.isdecimal() or len(colspan) > 4:
                return None
            column_count += max(1, int(colspan))
        return column_count

    own_parts = [
        part
        for part in table.find_all(["thead", "tbody", "tfoot", "tr", "th", "td"])
        if part.find_parent("table") is table
    ]
    rows = [part for part in own_parts if part.name == "tr"]
    if not rows or not has_only_children(table, ["colgroup", "thead", "tbody", "tr"]):
        return False
    if not all(
        has_only_children(colgroup, ["col"])
        and colgroup.find_previous_sibling(["thead", "tbody", "tr"]) is None
        for colgroup in table.find_all("colgroup", recursive=False)
    ):
        return False
    for part in own_parts:
        assert part.parent is not None
        if part.name == "tr":
            in_section = part.parent is table or part.parent.name in ["thead", "tbody"]
            is_valid = in_section and has_only_children(part, ["th", "td"])
        elif part.name in ["th", "td"]:
            is_valid = part.parent.name == "tr"
        else:
            is_valid = part.parent is table and has_only_children(part, ["tr"])
        if not is_valid:
            return False
    if table.find_parent(["a", "th", "td"]) is not None or "|" in table.get_text():
        return False
    for element in table.find_all(["a", "img"]):
        if any("|" in str(value) for value in element.attrs.values()):
            return False

    header_row, *later_rows = rows
    header_section = header_row.parent
    assert header_section is not None
    if len(get_cells(header_row)) < 2 or header_row.find("table") is not None:
        return False
    if header_row.find_previous_sibling() is not None:
        return False
    is_only_thead_row = header_section.name == "thead" and len(header_section.find_all("tr")) == 1
    if not is_only_thead_row and not is_all_th(header_row):
        return False

    header_column_count = get_column_count(header_row)
    if header_column_count is None:
        return False
    for row in later_rows:
        column_count = get_column_count(row)
        if column_count is None or not 1 <= column_count <= header_column_count:
            return False
        if row.find_previous_sibling() is not None:
            continue
        assert row.parent is not None
        if row.parent.name != "tbody" or header_section.name != "thead" or is_all_th(row):
            return False
    return True


class ZulipMarkdownConverter(markdownify.MarkdownConverter):
    """HTML-to-Markdown converter adapted to Zulip's Markdown.

    Zulip doesn't inline-render external images, so images become
    `[label](src)` links instead of broken `![alt](src)`.
    """

    def convert_img(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        src = el.get("src", "")
        alt = el.get("alt", "")
        # BeautifulSoup returns a list only for multi-valued attributes
        # (e.g. class), never for src or alt.
        assert isinstance(src, str)
        assert isinstance(alt, str)
        if not src:
            return alt
        url = sanitize_url(src)
        if not url:
            # Unlinkable src (e.g. data: URIs, unsafe schemes): emit just the
            # alt text rather than a bogus link.
            return alt
        label = alt or posixpath.basename(urlsplit(url).path)
        if not label:
            # No alt text, and no filename in the path to fall back on, as in
            # `<img src="https://example.com/?token=abc">`.
            return url
        if "a" in parent_tags:
            # Markdown has no nested links, so hand the label up for the
            # enclosing <a> to use as its text, with brackets stripped.
            return re.sub(r"\[|\]", "", label)
        return get_markdown_link_for_url(label, url)

    def convert_title(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        return ""

    @override
    def convert_soup(self, soup: BeautifulSoup) -> str:
        # Markdown tables can't nest, and their cells can't hold block
        # content. A table containing another table is page layout, unless
        # it is a data table. Convert a layout table's own rows and cells
        # as if they were <div>s. Do the same for a table inside a Markdown
        # table, so that its content lands in the enclosing cell.
        #
        # find_all returns outer tables first, so a table that still has a
        # <table> ancestor is inside one that was kept as a Markdown table.
        for table in soup.find_all("table"):
            is_nested = table.find_parent("table") is not None
            if not is_nested and (table.find("table") is None or is_data_table(table)):
                continue
            for part in table.find_all(["thead", "tbody", "tfoot", "tr", "th", "td"]):
                if part.find_parent("table") is table:
                    part.name = "div"
            table.name = "div"
        return super().convert_soup(soup)


def convert_html_to_markdown(
    html: str, *, converter_class: type[ZulipMarkdownConverter] = ZulipMarkdownConverter
) -> str:
    # A bare URL is expected input here (the text/html part of an incoming
    # email), but BeautifulSoup warns about it ("looks like a URL, not markup").
    # Suppress the warning so that expected input doesn't spam our logs.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MarkupResemblesLocatorWarning)
        converter = converter_class(
            # Zulip's Markdown supports only ATX headings, not Setext headings.
            heading_style="ATX",
            # Zulip's Markdown has no backslash escaping; it renders "\" as a
            # literal character.
            escape_asterisks=False,
            escape_underscores=False,
            # HTML treats a newline as insignificant whitespace, but Zulip
            # renders it as a line break. Collapse source newlines to spaces.
            # <br>, <pre>, and block-level elements still produce line breaks.
            wrap=True,
            # An effectively infinite width disables column wrapping. Don't
            # use None, which also disables wrapping but skips the pass that
            # strips indentation from lines following a <br>.
            wrap_width=sys.maxsize,
        )
        markdown: str = converter.convert(html).strip()
    return markdown
