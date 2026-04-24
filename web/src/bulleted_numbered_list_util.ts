export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

const bullet_pattern = /^(\s*[-*+] )/;

export const is_bulleted = (line: string): boolean => bullet_pattern.test(line);

export const get_bullet_prefix = (line: string): string => {
    const match = bullet_pattern.exec(line);
    return match?.[1] ?? "";
};

export const strip_bullet = (line: string): string => {
    const bullet_prefix = get_bullet_prefix(line);
    return line.slice(bullet_prefix.length);
};

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => /^\d+\. /.test(line);

export const strip_numbering = (line: string): string => line.slice(line.indexOf(" ") + 1);
