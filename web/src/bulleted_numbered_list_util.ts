export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

export const get_indent = (line: string): string => /^(\s*)/.exec(line)![1] ?? "";

const heading_pattern = /^#{1,6} /;
const quote_pattern = /^(?:>[ \t]*)+/;
const numbered_pattern = /^\d+\. /;

export const is_bulleted = (line: string): boolean =>
    line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ");

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => numbered_pattern.test(line);

export const strip_bullet = (line: string): string => line.slice(2);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);

export const is_list_item = (line: string): boolean => {
    const trimmed = line.trimStart();
    return is_bulleted(trimmed) || is_numbered(trimmed);
};

// Returns the prefix of a line, including leading indentation and any block/list marker
// (e.g., "  - ", "1. ", "> ", "# ", or "  "), so inline formatting applies to actual content.
export const get_prefix = (line: string): string => {
    let prefix = get_indent(line);
    let rest = line.slice(prefix.length);

    // Blockquote markers (e.g., "> ", ">> ")
    const quote_match = quote_pattern.exec(rest);
    if (quote_match !== null) {
        prefix += quote_match[0];
        rest = line.slice(prefix.length);
    }

    // Heading markers (e.g., "# ", "## ")
    const heading_match = heading_pattern.exec(rest);
    if (heading_match !== null) {
        prefix += heading_match[0];
        return prefix;
    }

    // List markers (e.g., "- ", "* ", "+ ", "1. ")
    if (is_bulleted(rest)) {
        prefix += rest.slice(0, 2);
        return prefix;
    }
    const numbered_match = numbered_pattern.exec(rest);
    if (numbered_match !== null) {
        prefix += numbered_match[0];
        return prefix;
    }

    return prefix;
};
