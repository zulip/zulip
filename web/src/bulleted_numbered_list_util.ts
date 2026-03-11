export const get_last_line = (text: string): string => text.slice(text.lastIndexOf("\n") + 1);

const BULLET_REGEX = /^\s*([*+-])\s/;
const NUMBERED_REGEX = /^\s*(\d+)\.\s/;

export const is_bulleted = (line: string): boolean => BULLET_REGEX.test(line);

// testing against regex for string with numbered syntax, that is,
// any string starting with digit/s followed by a period and space
export const is_numbered = (line: string): boolean => NUMBERED_REGEX.test(line);

export const strip_bullet = (line: string): string => line.replace(BULLET_REGEX, "");

export const strip_numbering = (line: string): string => line.replace(NUMBERED_REGEX, "");

export const get_bullet_prefix = (line: string): string | null => {
    const m = line.match(BULLET_REGEX);
    return m ? m[0] : null;
};

export const get_number_prefix_and_value = (
    line: string,
): {prefix: string; value: number} | null => {
    const m = line.match(NUMBERED_REGEX);
    if (!m) {
        return null;
    }
    const value = Number.parseInt(m[1]!, 10);
    return {prefix: m[0]!, value};
};
