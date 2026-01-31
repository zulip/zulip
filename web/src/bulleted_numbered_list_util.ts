export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

export const is_bulleted = (line: string): boolean =>
    line.startsWith("- ") || line.startsWith("* ") || line.startsWith("+ ");

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => /^\d+\. /.test(line);

export const strip_bullet = (line: string): string => line.slice(2);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);

// Check if a line is a list item (bulleted or numbered), accounting for indentation
export const is_list_item = (line: string): boolean => {
    const trimmed = line.trimStart();
    return is_bulleted(trimmed) || is_numbered(trimmed);
};

// Add two spaces of indentation to a line
export const indent_line = (line: string): string => "  " + line;

// Remove up to two spaces of indentation from a line
export const outdent_line = (line: string): string => {
    if (line.startsWith("  ")) {
        return line.slice(2);
    } else if (line.startsWith(" ")) {
        return line.slice(1);
    }
    return line;
};

