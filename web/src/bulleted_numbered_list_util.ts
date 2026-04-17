export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

export const get_indent = (line: string): string => /^(\s*)/.exec(line)![1] ?? "";

const numbered_pattern = /^\d+\. /;

export const is_bulleted = (line: string): boolean =>
    line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ");

export const is_numbered = (line: string): boolean => numbered_pattern.test(line);

// Returns the bulleted or numbered list prefix at the start of `line`
// (e.g., "- ", "1. "), or "" if the line is not part of a list.
export const get_prefix = (line: string): string => {
    if (is_bulleted(line)) {
        return line.slice(0, 2);
    }
    const numbered_match = numbered_pattern.exec(line);
    return numbered_match === null ? "" : numbered_match[0];
};

export const strip_bullet = (line: string): string => line.slice(2);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);
