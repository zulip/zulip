import * as compose_state from "./compose_state.ts";
import * as compose_textarea from "./compose_textarea.ts";

export const SPLIT_DELIMITER = "\n\n\n";
// Two consecutive blank lines, tolerating spaces/tabs on the blank lines, so
// that lines that only look blank still split the message.
const SPLIT_DELIMITER_REGEX = /\n[^\S\n]*\n[^\S\n]*\n/;
export const MAX_SPLIT_PARTS = 20;
let split_messages_enabled = false;

export function is_split_messages_enabled(): boolean {
    return split_messages_enabled;
}

let cached_input: string | undefined;
let cached_parts: string[] | undefined;

function invalidate_split_parts_cache(): void {
    cached_input = undefined;
    cached_parts = undefined;
}

export function set_split_messages_enabled(enable: boolean): void {
    if (split_messages_enabled !== enable) {
        invalidate_split_parts_cache(); // toggle changes the result
    }
    split_messages_enabled = enable;
}

// Returns index of the first delimiter which is not inside a code block.
export function delimiter_index_outside_code_block(content: string): number {
    const ranges = compose_textarea.get_code_block_ranges(content);
    const is_inside = (pos: number): boolean =>
        ranges.some(([start, end]) => pos >= start && pos < end);

    const regex = new RegExp(SPLIT_DELIMITER_REGEX, "g");
    let match;
    while ((match = regex.exec(content)) !== null) {
        if (!is_inside(match.index + 1)) {
            return match.index;
        }
        regex.lastIndex = match.index + 1;
    }
    return -1;
}

export function trim_except_whitespace_before_text(content: string): string {
    return content.replace(/^(\s*\n)+/, "").trimEnd();
}

export function split_message(raw_message_content: string): [string, string] {
    if (!is_split_messages_enabled()) {
        return [raw_message_content, ""];
    }
    // Trim leading newlines to avoid empty messages due to multiple delimiters.
    // Whitespace before text is markdown syntax for code blocks, so we should not trim it.
    const message_content = trim_except_whitespace_before_text(raw_message_content);

    // We do not wish to split inside code blocks, so we ignore delimiters inside code blocks.
    const index = delimiter_index_outside_code_block(message_content);
    if (index === -1) {
        return [message_content, ""];
    }
    const send_content = message_content.slice(0, index);
    const rest_content = message_content.slice(index);
    return [send_content, rest_content];
}

export function count_message_content_split_parts(
    message_content: string = compose_state.message_content(),
): number {
    return get_all_split_parts(message_content).length;
}

export function get_all_split_parts(message_content: string): string[] {
    if (cached_input === message_content && cached_parts !== undefined) {
        return cached_parts;
    }
    const parts: string[] = [];
    let remaining_content = message_content;
    while (remaining_content) {
        const [part, rest] = split_message(remaining_content);
        parts.push(part);
        remaining_content = rest;
    }
    cached_input = message_content;
    cached_parts = parts;
    return parts;
}

export function will_split_into_multiple_messages(
    message_content: string = compose_state.message_content(),
): boolean {
    if (!is_split_messages_enabled()) {
        return false;
    }
    // If there is a non-empty remaining part, splitting will occur.
    return split_message(message_content)[1] !== "";
}
