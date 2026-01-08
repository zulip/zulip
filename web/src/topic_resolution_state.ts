import {realm} from "./state_data.ts";

// Minimum character count for resolution message when required
export const MIN_RESOLUTION_MESSAGE_LENGTH = 10;

// State for pending topic resolution
let pending_resolution: {
    message_id: number;
    stream_id: number;
    topic: string;
    report_errors_in_global_banner: boolean;
} | null = null;

export function has_pending_resolution(): boolean {
    return pending_resolution !== null;
}

export function get_pending_resolution(): typeof pending_resolution {
    return pending_resolution;
}

export function set_pending_resolution(state: typeof pending_resolution): void {
    pending_resolution = state;
}

export function clear_pending_resolution_state(): void {
    pending_resolution = null;
}

export function is_message_requirement_enabled(): boolean {
    const setting = realm.realm_topic_resolution_message_requirement;
    return setting === "required" || setting === "optional";
}

export function is_message_required(): boolean {
    return realm.realm_topic_resolution_message_requirement === "required";
}

export function is_message_optional(): boolean {
    return realm.realm_topic_resolution_message_requirement === "optional";
}

export function is_resolve_via_move_allowed(): boolean {
    return realm.realm_topic_resolution_message_requirement !== "required";
}

/**
 * Strip markdown decorators from content to get the actual text length.
 * This removes block-level decorators that users might add via compose buttons:
 * - Quote blocks (> )
 * - Code blocks (``` or ~~~)
 * - Math blocks ($$)
 * - Spoiler blocks (```spoiler)
 *
 * Only counts the actual user-typed content, not the decorators themselves.
 */
export function strip_markdown_decorators(content: string): string {
    let result = content;

    // Remove code/math fence markers (```, ~~~, $$) on their own lines
    result = result.replaceAll(/^(`{3,}|~{3,}|\$\$).*$/gm, "");

    // Remove spoiler markers
    result = result.replaceAll(/^```spoiler.*$/gm, "");

    // Remove quote prefixes (including nested quotes like >> or > >)
    result = result.replaceAll(/^(?:>\s*)+/gm, "");

    // Collapse multiple whitespace and trim
    result = result.replaceAll(/\s+/g, " ").trim();

    return result;
}
