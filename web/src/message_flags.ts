import type {DebouncedFunc} from "lodash";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import {localstorage} from "./localstorage.ts";
import type {Message} from "./message_store.ts";
import * as starred_messages from "./starred_messages.ts";

const untracked_flag_entry_schema = z.object({
    add_ids: z.pipe(
        z.array(z.number()),
        z.transform((ids) => new Set(ids)),
    ),
    remove_ids: z.pipe(
        z.array(z.number()),
        z.transform((ids) => new Set(ids)),
    ),
});
const untracked_flag_record_schema = z.record(z.string(), untracked_flag_entry_schema);

type UntrackedFlagEntry = z.infer<typeof untracked_flag_entry_schema>;
type UntrackedFlagRecord = z.infer<typeof untracked_flag_record_schema>;

export function send_flag_update_for_messages(
    msg_ids: number[],
    flag: string,
    op: "add" | "remove",
): void {
    void channel.post({
        url: "/json/messages/flags",
        data: {
            messages: JSON.stringify(msg_ids),
            flag,
            op,
        },
        success() {
            mutate_local_untracked_flag_changes(flag, (changes) => {
                // Remove ids for which the latest change has been sent to the server.
                for (const id of msg_ids) {
                    changes.add_ids.delete(id);
                    changes.remove_ids.delete(id);
                }
                return changes;
            });
        },
        error() {
            mutate_local_untracked_flag_changes(flag, (changes) => {
                for (const id of msg_ids) {
                    if (op === "add") {
                        if (changes.remove_ids.has(id)) {
                            changes.remove_ids.delete(id);
                        } else {
                            changes.add_ids.add(id);
                        }
                    } else {
                        if (changes.add_ids.has(id)) {
                            changes.add_ids.delete(id);
                        } else {
                            changes.remove_ids.add(id);
                        }
                    }
                }
                return changes;
            });
        },
    });
}

export function send_flag_update_for_untracked_messages(): void {
    const process_entries = (entries: UntrackedFlagRecord): UntrackedFlagRecord | undefined => {
        for (const [flag, entry] of Object.entries(entries)) {
            if (entry.add_ids.size > 0) {
                send_flag_update_for_messages([...entry.add_ids], flag, "add");
            }
            if (entry.remove_ids.size > 0) {
                send_flag_update_for_messages([...entry.remove_ids], flag, "remove");
            }
        }
        // The above API calls are expected to succeed, but even if they fail,
        // we can still clear the untracked entries here since the failed ones
        // will be added back.
        return {};
    };
    mutate_all_local_untracked_flag_changes(process_entries);
}

export function mutate_local_untracked_flag_changes(
    flag: string,
    cb: (entries: UntrackedFlagEntry) => UntrackedFlagEntry | undefined,
): void {
    mutate_all_local_untracked_flag_changes((untracked_flag_entries) => {
        const new_entries = cb(
            untracked_flag_entries[flag] ?? {add_ids: new Set(), remove_ids: new Set()},
        );
        if (new_entries === undefined) {
            return undefined;
        }
        untracked_flag_entries[flag] = new_entries;
        return untracked_flag_entries;
    });
}

export function mutate_all_local_untracked_flag_changes(
    cb: (entries: UntrackedFlagRecord) => UntrackedFlagRecord | undefined,
): void {
    if (!localstorage.supported()) {
        return;
    }
    const ls = localstorage();
    const untracked_flag_entries_value = ls.get("untracked_flag_entries");
    const result = untracked_flag_record_schema.safeParse(untracked_flag_entries_value);

    const untracked_flag_entries = result.success ? result.data : {};
    const changed_entries = cb(untracked_flag_entries);
    if (changed_entries === undefined) {
        return;
    }

    // Convert Sets back to arrays for storage
    const entries_array: Record<string, {add_ids: number[]; remove_ids: number[]}> = {};
    for (const flag of Object.keys(changed_entries)) {
        assert(changed_entries[flag] !== undefined);
        const encode_entry = {
            add_ids: [...changed_entries[flag].add_ids],
            remove_ids: [...changed_entries[flag].remove_ids],
        };
        entries_array[flag] = encode_entry;
    }
    ls.set("untracked_flag_entries", entries_array);
}

export let _unread_batch_size = 1000;

export function rewire__unread_batch_size(value: typeof _unread_batch_size): void {
    _unread_batch_size = value;
}

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
        allow_empty_topic_name: true,
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
