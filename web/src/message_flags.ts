import type {DebouncedFunc} from "lodash";
import _ from "lodash";
import {z} from "zod";

import * as channel from "./channel";
import type {Message} from "./message_store";
import * as starred_messages from "./starred_messages";

export function send_flag_update_for_messages(msg_ids: number[], flag: string, op: string): void {
    void channel.post({
        url: "/json/messages/flags",
        data: {
            messages: JSON.stringify(msg_ids),
            flag,
            op,
        },
    });
}
export const _unread_batch_size = 1000;

export const send_read = (function () {
    let queue: Message[] = [];
    let start: DebouncedFunc<() => void>;
    function server_request(): void {
        // Wait for server IDs before sending flags
        const real_msgs = queue.filter((msg) => !msg.locally_echoed);
        const real_msg_ids = real_msgs.map((msg) => msg.id);

        if (real_msg_ids.length === 0) {
            setTimeout(start, 100);
            return;
        }

        const real_msg_ids_batch = real_msg_ids.slice(0, _unread_batch_size);

        // We have some real IDs.  If there are any left in the queue when this
        // call finishes, they will be handled in the success callback.

        void channel.post({
            url: "/json/messages/flags",
            data: {messages: JSON.stringify(real_msg_ids_batch), op: "add", flag: "read"},
            success() {
                const batch_set = new Set(real_msg_ids_batch);
                queue = queue.filter((message) => !batch_set.has(message.id));

                if (queue.length > 0) {
                    start();
                }
            },
        });
    }

    start = _.throttle(server_request, 1000);

    function add(messages: Message[]): void {
        queue = [...queue, ...messages];
        start();
    }

    return add;
})();

export function mark_as_read(message_ids: number[]): void {
    send_flag_update_for_messages(message_ids, "read", "add");
}

export function mark_as_unread(message_ids: number[]): void {
    send_flag_update_for_messages(message_ids, "read", "remove");
}

export function save_collapsed(message: Message): void {
    send_flag_update_for_messages([message.id], "collapsed", "add");
}

export function save_uncollapsed(message: Message): void {
    send_flag_update_for_messages([message.id], "collapsed", "remove");
}

export function unstar_all_messages(): void {
    const starred_msg_ids = starred_messages.get_starred_msg_ids();
    send_flag_update_for_messages(starred_msg_ids, "starred", "remove");
}

// While we're parsing message objects, our code only looks at the
// IDs. TODO: Use a shared zod schema for parsing messages if/when
// message_fetch.ts parses message objects using zod.
const message_response_schema = z.object({
    messages: z.array(
        z.object({
            id: z.number(),
        }),
    ),
});

export function unstar_all_messages_in_topic(stream_id: number, topic: string): void {
    const data = {
        anchor: "newest",
        // In the unlikely event the user has >1000 starred messages
        // in a topic, this won't find them all. This is probably an
        // acceptable bug; one can do it multiple times, and we avoid
        // creating an API endpoint just for this very minor feature.
        num_before: 1000,
        num_after: 0,
        narrow: JSON.stringify([
            {operator: "channel", operand: stream_id},
            {operator: "topic", operand: topic},
            {operator: "is", operand: "starred"},
        ]),
    };

    void channel.get({
        url: "/json/messages",
        data,
        success(raw_data) {
            const data = message_response_schema.parse(raw_data);
            const messages = data.messages;
            const starred_message_ids = messages.map((message) => message.id);
            send_flag_update_for_messages(starred_message_ids, "starred", "remove");
        },
    });
}
