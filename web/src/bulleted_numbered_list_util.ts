export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

export const is_bulleted = (line: string): boolean => {
    const trimmed_line = line.trimStart();
    return trimmed_line.startsWith("- ") || trimmed_line.startsWith("* ") || trimmed_line.startsWith("+ ");
};

// testing against regex for string with numbered syntax, that is,
// any string starting with optional whitespace, then digit/s followed by a period and space
export const is_numbered = (line: string): boolean => /^\s*\d+\. /.test(line);

export const strip_bullet = (line: string): string => line.slice(2);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);
