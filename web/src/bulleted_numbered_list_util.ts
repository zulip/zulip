export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

export const is_bulleted = (line: string): boolean =>
    line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ");

// look for all consecutive whitespace characters at the beginning of the line
export const get_indentation = (line: string): string => /^\s*/.exec(line)?.[0] ?? "";

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => /^\d+\. /.test(line);

export const strip_bullet = (line: string): string => line.slice(2);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);
