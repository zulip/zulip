export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

// look for all consecutive whitespace characters at the beginning of the line
export const get_indentation = (line: string): string => /^\s*/.exec(line)?.[0] ?? "";

// look if the line starts with bullet syntaxes ("- ", "* ", "+ "),
// after trimming the leading whitespace characters (indentation handling)
export const is_bulleted = (line: string): boolean => {
    const trimmed_line = line.trimStart();
    return (
        trimmed_line.startsWith("- ") ||
        trimmed_line.startsWith("* ") ||
        trimmed_line.startsWith("+ ")
    );
};

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => /^\s*\d+\. /.test(line);

export const strip_bullet = (line: string): string => {
    const trimmed_line = line.trimStart();
    return trimmed_line.slice(2);
};

export const strip_numbering = (line: string): string => {
    const trimmed_line = line.trimStart();
    return trimmed_line.slice(trimmed_line.indexOf(" ") + 1);
};
