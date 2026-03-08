import assert from "minimalistic-assert";

import * as channel from "./channel.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_store from "./message_store.ts";
import {the} from "./util.ts";

export function get_raw_content_for_messages(
    message_ids: number[],
    on_success: (raw_content_arr: string[]) => void,
    on_error: () => void,
    timeout?: number,
): void {
    const missing_ids: number[] = [];
    const raw_content_arr: string[] = Array.from({length: message_ids.length});

    // We fill what we can from the store
    for (const [i, id] of message_ids.entries()) {
        const message = message_store.get(id);
        assert(message !== undefined);
        if (message.raw_content) {
            raw_content_arr[i] = message.raw_content;
        } else {
            missing_ids.push(id);
        }
    }

    if (missing_ids.length === 0) {
        on_success(raw_content_arr);
        return;
    }

    channel.get({
        url: "/json/messages",
        data: {
            allow_empty_topic_name: true,
            apply_markdown: false,
            message_ids: JSON.stringify(missing_ids),
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
        timeout,
        error: on_error,
    });
}

export function get_raw_content_for_single_message(
    message_id: number,
    on_success: (raw_content: string) => void,
    on_error: () => void,
    timeout?: number,
): void {
    get_raw_content_for_messages(
        [message_id],
        (raw_content_arr: string[]) => {
            on_success(the(raw_content_arr));
        },
        () => {
            on_error();
        },
        timeout,
    );
}
