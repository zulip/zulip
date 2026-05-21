import assert from "minimalistic-assert";

import * as channel from "./channel.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_store from "./message_store.ts";

// Process a batch response from GET /messages, filling raw_content_arr
// for messages that were returned and returning data for any message IDs
// that were requested but not present in the response.
function fill_from_batch_response(
    raw_data: unknown,
    message_ids: number[],
    raw_content_arr: string[],
): {array_index: number; message_id: number}[] {
    const data = message_fetch.message_ids_response_schema.parse(raw_data);
    const fetched_raw_content_map = new Map<number, string>();
    for (const raw_message of data.messages) {
        const parsed_message =
            message_store.single_message_content_schema.shape.message.parse(raw_message);
        message_store.maybe_update_raw_content(raw_message.id, parsed_message.content);
        fetched_raw_content_map.set(raw_message.id, parsed_message.content);
    }

    const missing_entries: {array_index: number; message_id: number}[] = [];
    for (const [i, id] of message_ids.entries()) {
        if (raw_content_arr[i] !== undefined) {
            continue;
        }
        const fetched = fetched_raw_content_map.get(id);
        if (fetched !== undefined) {
            raw_content_arr[i] = fetched;
        } else {
            missing_entries.push({array_index: i, message_id: id});
        }
    }
    return missing_entries;
}

function fetch_messages_individually(info: {
    entries_to_fetch: {array_index: number; message_id: number}[];
    raw_content_arr: string[];
    on_success: (raw_content_arr: string[]) => void;
    on_error: () => void;
    timeout_ms?: number | undefined;
}): void {
    const {entries_to_fetch, raw_content_arr, on_success, on_error, timeout_ms} = info;
    let completed = 0;
    let had_error = false;

    // Calls on_success once all have completed, or on_error on the first failure.
    function fetch_one({array_index, message_id}: {array_index: number; message_id: number}): void {
        channel.get({
            url: "/json/messages/" + message_id,
            data: {allow_empty_topic_name: true, apply_markdown: false},
            success(raw_data) {
                const data = message_store.single_message_content_schema.parse(raw_data);
                message_store.maybe_update_raw_content(message_id, data.message.content);
                raw_content_arr[array_index] = data.message.content;
                completed += 1;
                if (completed === entries_to_fetch.length) {
                    on_success(raw_content_arr);
                }
            },
            timeout: timeout_ms,
            error() {
                if (!had_error) {
                    had_error = true;
                    on_error();
                }
            },
        });
    }

    for (const entry of entries_to_fetch) {
        fetch_one(entry);
    }
}

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

    channel.get({
        url: "/json/messages",
        data: {
            allow_empty_topic_name: true,
            apply_markdown: false,
            message_ids: JSON.stringify(message_ids_that_require_fetching),
        },
        success(raw_data) {
            const missing_raw_content = fill_from_batch_response(
                raw_data,
                message_ids,
                raw_content_arr,
            );

            if (missing_raw_content.length === 0) {
                on_success(raw_content_arr);
                return;
            }

            // Retry messages still missing raw_content with the
            // channels:public narrow.
            const missing_ids = missing_raw_content.map((e) => e.message_id);
            channel.get({
                url: "/json/messages",
                data: {
                    allow_empty_topic_name: true,
                    apply_markdown: false,
                    message_ids: JSON.stringify(missing_ids),
                    narrow: JSON.stringify([{operator: "channels", operand: "public"}]),
                },
                success(retry_raw_data) {
                    const still_missing_raw_content = fill_from_batch_response(
                        retry_raw_data,
                        message_ids,
                        raw_content_arr,
                    );

                    if (still_missing_raw_content.length === 0) {
                        on_success(raw_content_arr);
                        return;
                    }

                    // Any messages still missing raw_content are
                    // from private channels with shared history
                    // where the user was subscribed after the
                    // messages were sent.
                    fetch_messages_individually({
                        entries_to_fetch: still_missing_raw_content,
                        raw_content_arr,
                        on_success,
                        on_error,
                        timeout_ms,
                    });
                },
                timeout: timeout_ms,
                error: on_error,
            });
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
