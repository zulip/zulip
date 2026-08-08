import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";

// Keep in sync with zerver.lib.narrow.ok_to_include_history.
const history_enabling_narrow_term_schema = z.object({
    operator: z.string(),
    operand: z.union([z.number(), z.string(), z.array(z.number())]),
    negated: z.optional(z.boolean()),
});

function is_history_enabling_term(
    term: z.infer<typeof history_enabling_narrow_term_schema>,
): boolean {
    if (term.negated) {
        return false;
    }
    if (term.operator === "channel" || term.operator === "stream") {
        return true;
    }
    return (
        term.operator === "channels" && (term.operand === "public" || term.operand === "web-public")
    );
}

// Returns a JSON narrow for GET /messages that enables shared history
// (channel/stream, or channels:public|web-public). Returns undefined
// when no such terms are present so the caller can omit the parameter.
function get_history_enabling_narrow_for_raw_content_fetch(): string | undefined {
    const filter = narrow_state.filter();
    if (filter === undefined) {
        return undefined;
    }

    const encoded = message_fetch.get_narrow_for_message_fetch(filter);
    if (encoded === "") {
        return undefined;
    }

    const history_terms = z
        .array(history_enabling_narrow_term_schema)
        .parse(JSON.parse(encoded))
        .filter((term) => is_history_enabling_term(term));

    if (history_terms.length === 0) {
        return undefined;
    }
    return JSON.stringify(history_terms);
}

export function get_raw_content_for_messages(info: {
    message_ids: number[];
    on_success: (raw_content_arr: (string | undefined)[]) => void;
    on_error: () => void;
    timeout_ms?: number | undefined;
}): void {
    const {message_ids, on_success, on_error, timeout_ms} = info;
    const message_ids_that_require_fetching: number[] = [];
    const raw_content_arr: (string | undefined)[] = Array.from({length: message_ids.length});
    const messages: Message[] = [];

    // We fill what we can from message_store.
    for (const [i, id] of message_ids.entries()) {
        const message = message_store.get(id);
        assert(message !== undefined);
        messages.push(message);
        if (message.raw_content) {
            raw_content_arr[i] = message.raw_content;
        } else {
            message_ids_that_require_fetching.push(id);
        }
    }

    if (message_ids_that_require_fetching.length === 0) {
        on_success(raw_content_arr);
        return;
    }

    // GET /messages with message_ids uses personal history unless a
    // history-enabling narrow is passed
    // (https://zulip.com/api/get-messages#parameter-narrow).
    const narrow = get_history_enabling_narrow_for_raw_content_fetch();

    channel.get({
        url: "/json/messages",
        data: {
            allow_empty_topic_name: true,
            apply_markdown: false,
            message_ids: JSON.stringify(message_ids_that_require_fetching),
            ...(narrow !== undefined && {narrow}),
        },
        success(raw_data) {
            const data = message_fetch.message_ids_response_schema.parse(raw_data);
            const fetched_raw_content_map = new Map<number, string>();
            for (const raw_message of data.messages) {
                const parsed_message =
                    message_store.single_message_content_schema.shape.message.parse(raw_message);
                message_store.maybe_update_raw_content(raw_message.id, parsed_message.content);
                fetched_raw_content_map.set(raw_message.id, parsed_message.content);
            }

            // Fill remaining holes in request order. Missing ids stay unset.
            for (const [i, id] of message_ids.entries()) {
                if (raw_content_arr[i] !== undefined) {
                    continue;
                }
                const fetched = fetched_raw_content_map.get(id);
                if (fetched !== undefined) {
                    raw_content_arr[i] = fetched;
                    continue;
                }
                const message = messages[i]!;
                if (message.raw_content !== undefined) {
                    raw_content_arr[i] = message.raw_content;
                }
            }

            on_success(raw_content_arr);
        },
        timeout: timeout_ms,
        error: on_error,
    });
}

export function get_raw_content_for_single_message(info: {
    message_id: number;
    on_success: (raw_content: string) => void;
    on_error: () => void;
    timeout_ms?: number;
}): void {
    const {message_id, on_success, on_error, timeout_ms} = info;
    const message = message_store.get(message_id);
    assert(message !== undefined);
    if (message.raw_content) {
        on_success(message.raw_content);
        return;
    }

    // The single-message endpoint handles messages that the user has
    // access to, but are not in the user's message history, e.g.,
    // private channel messages with shared history sent prior to the
    // user being subscribed to the channel.
    channel.get({
        url: "/json/messages/" + message_id,
        data: {allow_empty_topic_name: true, apply_markdown: false},
        success(raw_data) {
            const data = message_store.single_message_content_schema.parse(raw_data);
            message_store.maybe_update_raw_content(message_id, data.message.content);
            on_success(data.message.content);
        },
        timeout: timeout_ms,
        error: on_error,
    });
}
