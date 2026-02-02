export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

export const is_bulleted = (line: string): boolean =>
    line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ");

// Check if a line is an indented bulleted list item
export const is_indented_bulleted = (line: string): boolean => {
    const trimmed = line.trimStart();
    return line.length > trimmed.length && is_bulleted(trimmed);
};

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => /^\d+\. /.test(line);

// Check if a line is an indented numbered list item
export const is_indented_numbered = (line: string): boolean => {
    const trimmed = line.trimStart();
    return line.length > trimmed.length && is_numbered(trimmed);
};

// Get the indentation (leading spaces) from a line
export const get_indentation = (line: string): string => {
    // Regex always matches since \s* can match zero characters
    const match = /^(\s*)/.exec(line);
    return match![1]!;
};

export const strip_bullet = (line: string): string => line.slice(2);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);
