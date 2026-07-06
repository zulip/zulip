import assert from "minimalistic-assert";

import * as channel from "./channel.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_store from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";

export function get_raw_content_for_messages(info: {
    message_ids: number[];
    on_success: (raw_content_arr: string[]) => void;
    on_error: () => void;
    timeout_ms?: number | undefined;
}): void {
    const {message_ids, on_success, on_error, timeout_ms} = info;
    const message_ids_that_require_fetching: number[] = [];
    const raw_content_arr: string[] = Array.from({length: message_ids.length});

    // We fill what we can from the store.
    for (const [i, id] of message_ids.entries()) {
        const message = message_store.get(id);
        assert(message !== undefined);
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

    // Multi-message quoting happens from the message feed. A user's
    // personal message history does not include channel messages from
    // before they subscribed
    // (https://zulip.com/api/get-messages). Passing the current
    // narrow lets GET /messages search shared history instead of only
    // that personal history, so we get messages that lack a
    // UserMessage row (e.g. unsubscribed public channels, or private
    // channels with shared history before the user subscribed). See
    // https://zulip.com/api/get-messages#parameter-narrow.
    const filter = narrow_state.filter();
    const narrow = filter !== undefined ? message_fetch.get_narrow_for_message_fetch(filter) : "";

    channel.get({
        url: "/json/messages",
        data: {
            allow_empty_topic_name: true,
            apply_markdown: false,
            message_ids: JSON.stringify(message_ids_that_require_fetching),
            ...(narrow !== "" ? {narrow} : {}),
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

            // Fill the remaining holes in the final array
            for (const [i, id] of message_ids.entries()) {
                raw_content_arr[i] ??= fetched_raw_content_map.get(id)!;
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
