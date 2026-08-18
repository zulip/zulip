import {get_immutable_message, get_mutable_message} from "../../src/message_store.ts";
import type {Message, ReadonlyMessage} from "../../src/message_store.ts";

export function get_returns_readonly_view(id: number): ReadonlyMessage | undefined {
    return get_immutable_message(id);
}

export function get_mutable_returns_writable(id: number): Message | undefined {
    const message = get_mutable_message(id);
    if (message !== undefined) {
        message.content = "writable";
    }
    return message;
}

export function cannot_assign_through_immutable_get(id: number): void {
    const msg = get_immutable_message(id);
    if (msg === undefined) {
        return;
    }
    // @ts-expect-error ReadonlyMessage forbids assigning content.
    msg.content = "nope";
    // @ts-expect-error ReadonlyMessage forbids assigning unread.
    msg.unread = false;
    // @ts-expect-error ReadonlyMessage forbids assigning raw_content.
    msg.raw_content = "x";
}

function takes_mutable_message(message: Message): void {
    message.content = "rogue";
}

function takes_readonly_message(message: ReadonlyMessage): string {
    return message.content;
}

/**
 * Compile-time tests for ReadonlyMessage. tsc is the runner; this is
 * never called at runtime.
 */
export function readonly_message_type_tests(
    stream_msg: Extract<ReadonlyMessage, {type: "stream"}>,
    private_msg: Extract<ReadonlyMessage, {type: "private"}>,
    msg: ReadonlyMessage,
): string {
    const stream_reads =
        msg.type === "stream"
            ? [msg.stream_id, msg.topic, msg.stream, String(msg.is_stream)]
            : [msg.to_user_ids, msg.pm_with_url, msg.display_reply_to, String(msg.is_private)];

    const reads = [
        msg.id,
        msg.content,
        msg.sender_id,
        msg.sender_email,
        msg.sender_full_name,
        String(msg.unread),
        String(msg.starred),
        String(msg.mentioned),
        String(msg.sent_by_me),
        msg.reply_to,
        msg.timestamp,
        msg.raw_content ?? "",
        String(msg.locally_echoed ?? false),
        String(msg.clean_reactions.size),
        stream_msg.stream_id,
        stream_msg.topic,
        private_msg.to_user_ids,
        ...stream_reads,
    ];

    takes_readonly_message(msg);
    takes_readonly_message(stream_msg);
    takes_readonly_message(private_msg);

    // The #13347 hole: this type-checks, then mutates the singleton.
    takes_mutable_message(msg);

    // @ts-expect-error ReadonlyMessage forbids assigning id.
    msg.id = 0;
    // @ts-expect-error ReadonlyMessage forbids assigning content.
    msg.content = "mutated";
    // @ts-expect-error ReadonlyMessage forbids assigning raw_content.
    msg.raw_content = "x";
    // @ts-expect-error ReadonlyMessage forbids assigning unread.
    msg.unread = false;
    // @ts-expect-error ReadonlyMessage forbids assigning starred.
    msg.starred = true;
    // @ts-expect-error ReadonlyMessage forbids assigning mentioned.
    msg.mentioned = true;
    // @ts-expect-error ReadonlyMessage forbids assigning mentioned_me_directly.
    msg.mentioned_me_directly = true;
    // @ts-expect-error ReadonlyMessage forbids assigning collapsed.
    msg.collapsed = true;
    // @ts-expect-error ReadonlyMessage forbids assigning sent_by_me.
    msg.sent_by_me = false;
    // @ts-expect-error ReadonlyMessage forbids assigning reply_to.
    msg.reply_to = "";
    // @ts-expect-error ReadonlyMessage forbids assigning sender_full_name.
    msg.sender_full_name = "x";
    // @ts-expect-error ReadonlyMessage forbids assigning sender_id.
    msg.sender_id = 0;
    // @ts-expect-error ReadonlyMessage forbids assigning sender_email.
    msg.sender_email = "x";
    // @ts-expect-error ReadonlyMessage forbids assigning timestamp.
    msg.timestamp = 0;
    // @ts-expect-error ReadonlyMessage forbids assigning locally_echoed.
    msg.locally_echoed = true;
    // @ts-expect-error ReadonlyMessage forbids assigning local_edit_timestamp.
    msg.local_edit_timestamp = 1;
    // @ts-expect-error ReadonlyMessage forbids assigning flags.
    msg.flags = [];
    // @ts-expect-error ReadonlyMessage forbids replacing clean_reactions.
    msg.clean_reactions = new Map();
    // @ts-expect-error ReadonlyMessage forbids assigning type.
    msg.type = "stream";

    // @ts-expect-error topic is not on a private ReadonlyMessage.
    void private_msg.topic;
    // @ts-expect-error to_user_ids is not on a stream ReadonlyMessage.
    void stream_msg.to_user_ids;

    // @ts-expect-error ReadonlyMessage forbids assigning topic.
    stream_msg.topic = "other";
    // @ts-expect-error ReadonlyMessage forbids assigning stream_id.
    stream_msg.stream_id = 0;
    // @ts-expect-error ReadonlyMessage forbids assigning to_user_ids.
    private_msg.to_user_ids = "";

    // Shallow Readonly: nested arrays and Maps are still mutable.
    if (msg.flags !== undefined) {
        msg.flags.push("read");
    }
    msg.clean_reactions.clear();

    return reads.join(",");
}
