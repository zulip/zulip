import * as compose_state from "./compose_state";
import * as compose_textarea from "./compose_textarea";

export const SPLIT_DELIMITER = "\n\n\n";
let split_messages_enabled = false;

export function is_split_messages_enabled(): boolean {
    return split_messages_enabled;
}

export function set_split_messages_enabled(enable: boolean): void {
    split_messages_enabled = enable;
}

// Returns index of the first delimiter which is not inside a code block.
export function delimiter_index_outside_code_block(content: string): number {
    let index = content.indexOf(SPLIT_DELIMITER);
    while (index !== -1) {
        if (!compose_textarea.position_inside_code_block(content, index + 1)) {
            return index;
        }
        index = content.indexOf(SPLIT_DELIMITER, index + 1);
    }
    return -1;
}

export function trim_except_whitespace_before_text(content: string): string {
    return content.replace(/^(\n|\s*\n)+/, "").trimEnd();
}

export function split_message(raw_message_content: string): [string, string] {
    if (!is_split_messages_enabled()) {
        return [raw_message_content, ""];
    }
    // trimming is required to avoid empty messages due to multiple delimiters.
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

export function count_message_content_split_parts(): number {
    const message_content = compose_state.message_content();
    let count = 1;
    let parts = split_message(message_content);
    while (parts[1]) {
        count += 1;
        parts = split_message(parts[1]);
    }
    return count;
}

export function will_split_into_multiple_messages(): boolean {
    if (!is_split_messages_enabled()) {
        return false;
    }
    // If there is a non-empty remaining part, splitting will occur.
    return Boolean(split_message(compose_state.message_content())[1]);
}
