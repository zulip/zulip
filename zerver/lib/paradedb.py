import html
import re
from dataclasses import dataclass


@dataclass
class QueryAtom:
    original_string: str
    html_escaped_string: str
    is_phrase: bool


def search_operand_to_tantivy_query(operand: str) -> str | None:
    # TODO: Implement better parsing here so that we can support
    # more complex queries; consider exposing some of the tantivy
    # query language.
    #
    # A basic case that should at least be supported is search with phrase
    # terms and word terms such as
    # word1 "phrase with spaces" word2 "another phrase"
    # For now this only supports:
    # 1) single phrase search: "phrase with spaces"
    # 2) words search: word1 word2 word3

    # https://docs.paradedb.com/documentation/full-text/term#special-characters
    special_chars = {
        "'",
        '"',
        "+",
        "^",
        "`",
        ":",
        "{",
        "}",
        "[",
        "]",
        "(",
        ")",
        "~",
        "!",
        "\\",
        "*",
    }
    # These aren't listed, but empirically seem to be clearly special symbols that need escaping
    # to be treated literally.
    # https://github.com/paradedb/paradedb/pull/1827
    special_chars.update({"<", ">"})

    # The operand may have the form "<some content>", not necessarily alphanumeric.
    # That's treated as a phrase search.
    match = re.match(r'^"(.*)"$', operand)
    if match:
        extracted = match.group(1)  # Return the content inside the quotes
        if not extracted:
            return None
        if '"' in extracted:
            # It doesn't seem important to support this in phrase search
            # as it might complicate the parsing logic in terms of figuring out the
            # boundaries of the phrase.
            return None

        # Escape HTML as HTML symbols that were typed by the user in a message
        # end up HTML-escaped in rendered_content. " and ' are preserved literally
        # in rendered_content, so here we also need to be careful and html.escape(..., quote=False)
        # to preserve them.
        #
        # Note: Until the TODO below is resolved however, these special characters
        # are not allowed in the search anyway.
        html_escaped = html.escape(extracted, quote=False)

        # TODO: The exact set of characters that may need escaping and how exactly
        # to escape them is still somewhat unclear. For now, just don't allow any
        # special characters. Add proper escaping when possible.
        if special_chars.intersection(html_escaped):
            # TODO: Alternatively, we could just remove the chars. Counterpoint: phrase
            # search is supposed to be very literal, so just clearly refusing to accept
            # the input might be better than altering the search.
            return None

        query_atoms = [
            QueryAtom(original_string=extracted, html_escaped_string=html_escaped, is_phrase=True)
        ]
    else:
        # The operand has the form
        # word1 word2 word3
        # where each word is a single word. Zulip's interpretation of this
        # search is "message contains all of these words in concat(subject, rendered_content)".
        #
        # The tantivy query reflecting that can be formed as:
        # (rendered_content:word1 OR subject:word1) AND (rendered_content:word2 OR subject:word2)
        # AND (rendered_content:word3 OR subject:word3)
        query_atoms = []

        # Ignore special characters by stripping them out of the words.
        # TODO: Consider just escaping them once we fully understand how to do that
        # correctly and for which characters exactly.
        for word in operand.split():
            word = word.strip()
            word = "".join(char for char in word if char not in special_chars)
            html_escaped_word = html.escape(word, quote=False)
            query_atoms.append(
                QueryAtom(
                    original_string=word, html_escaped_string=html_escaped_word, is_phrase=False
                )
            )

    or_conditions: list[str] = []
    for query_atom in query_atoms:
        # In Zulip, .rendered_content contains HTML-escaped content from the user, while .subject doesn't
        # escape HTML and thus contains the original content as entered by the user.
        # For that reason, QueryAtom contains both HTML escaped and original versions of the search query.
        # We want to match rendered_content against the HTML escaped version, but subject against the original.
        #
        # E.g. if we are being queried for <b>hello</b>, we want to search for &lt;b&gt;hello&lt;/b&gt in
        # rendered_content, but <b>hello</b> in subject. In practice, punctuation seems mostly ignored in our
        # tantivy queries on the index with English stemming, so this is a fairly theoretical technicality;
        # but might matter if we change/add tokenizers in the future.
        if query_atom.is_phrase:
            assert (
                len(query_atoms) == 1
            ), "Phrase search doesn't support anything else than a single phrase in the query"
            or_conditions.append(
                f'(rendered_content:"{query_atom.html_escaped_string}" OR subject:"{query_atom.original_string}")'
            )
        else:
            or_conditions.append(
                f"(rendered_content:{query_atom.html_escaped_string} OR subject:{query_atom.original_string})"
            )

    final_query = " AND ".join(or_conditions)
    return final_query
