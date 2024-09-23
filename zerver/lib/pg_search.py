import html
import re


def search_operand_to_tantivy_query(operand: str) -> str | None:
    # TODO: Implement better parsing here so that we can support
    # more complex queries; consider exposing some of the tantivy
    # query language.
    # A basic case that should at least be supported is search with phrase
    # terms and word terms such as
    # word1 "phrase with spaces" word2 "another phrase"
    # For now this only supports:
    # 1) single phrase search: "phrase with spaces"
    # 2) words search: word1 word2 word3

    # The operand may have the form "<some content>", not necessarily alphanumeric.
    # That's treated as a phrase search.
    match = re.match(r'^"(.*)"$', operand)
    if match:
        extracted = match.group(1)  # Return the content inside the quotes
        if not extracted:
            return None
        if '"' in extracted:
            # " is not supperted, as it gets escaped by escaping html, but
            # is not escaped in rendered_content.
            # TODO: fix this quirk.
            return None
        # TODO: sanitize the extracted content further, by escaping special tantivy characters. See
        # https://docs.paradedb.com/api-reference/full-text/term#special-characters
        query_string = f'"{html.escape(extracted)}"'
    else:
        if not all(char.isalnum() or char.isspace() for char in operand):
            return None

        # The operand has the form
        # word1 word2 word3
        # where each word is a single word. Zulip's interpretation of this
        # search is "message contains all of these words".
        #
        # The tantivy query reflecting that can be concisely formed as
        # (+word1 +word2 +word3)
        # as the + syntax makes each word a required match.
        words = operand.split()
        query_string = " ".join(f"+{word}" for word in words)
        query_string = f"({query_string})"

    final_query = f"rendered_content:{query_string} OR subject:{query_string}"
    return final_query
