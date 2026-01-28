import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import type {RawLocalMessage} from "./echo.ts";
import * as hash_util from "./hash_util.ts";
import type {LocalMessage, NewMessage, ProcessedMessage} from "./message_helper.ts";
import type {TimeFormattedReminder} from "./message_reminder.ts";
import * as muted_users from "./muted_users.ts";
import * as people from "./people.ts";
import * as stream_data from "./stream_data.ts";
import * as topic_link_util from "./topic_link_util.ts";
import {topic_link_schema} from "./types.ts";
import type {UserStatusEmojiInfo} from "./user_status.ts";
import * as util from "./util.ts";

const stored_messages = new Map<number, ProcessedMessage>();

const matched_message_schema = z.object({
    match_content: z.optional(z.string()),
    match_subject: z.optional(z.string()),
});

export type MatchedMessage = z.infer<typeof matched_message_schema>;

const message_reaction_type_schema = z.enum(["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]);

export type MessageReactionType = z.infer<typeof message_reaction_type_schema>;

const display_recipient_user_schema = z.object({
    email: z.string(),
    full_name: z.string(),
    id: z.number(),
});

export type DisplayRecipientUser = z.infer<typeof display_recipient_user_schema>;

const display_recipient_schema = z.union([z.string(), z.array(display_recipient_user_schema)]);

export type DisplayRecipient = z.infer<typeof display_recipient_schema>;

const message_edit_history_entry_schema = z.object({
    user_id: z.nullable(z.number()),
    timestamp: z.number(),
    prev_content: z.optional(z.string()),
    prev_rendered_content: z.optional(z.string()),
    prev_stream: z.optional(z.number()),
    prev_topic: z.optional(z.string()),
    stream: z.optional(z.number()),
    topic: z.optional(z.string()),
});

export type MessageEditHistoryEntry = z.infer<typeof message_edit_history_entry_schema>;

const message_reaction_schema = z.object({
    emoji_name: z.string(),
    emoji_code: z.string(),
    reaction_type: message_reaction_type_schema,
    user_id: z.number(),
});

export type MessageReaction = z.infer<typeof message_reaction_schema>;

export const single_message_content_schema = z.object({
    message: z.object({
        content: z.string(),
        content_type: z.enum(["text/html", "text/x-markdown"]),
    }),
});

export const submessage_schema = z.object({
    id: z.number(),
    sender_id: z.number(),
    message_id: z.number(),
    content: z.string(),
    msg_type: z.string(),
});

export const raw_message_schema = z.intersection(
    z.intersection(
        z.object({
            avatar_url: z.nullable(z.string()),
            client: z.string(),
            content: z.string(),
            content_type: z.literal("text/html"),
            display_recipient: display_recipient_schema,
            edit_history: z.optional(z.array(message_edit_history_entry_schema)),
            id: z.number(),
            is_me_message: z.boolean(),
            last_edit_timestamp: z.optional(z.number()),
            last_moved_timestamp: z.optional(z.number()),
            reactions: z.array(message_reaction_schema),
            sender_email: z.string(),
            sender_full_name: z.string(),
            sender_id: z.number(),
            // The web app doesn't use sender_realm_str; ignore.
            // sender_realm_str: z.string(),
            submessages: z.array(submessage_schema),
            timestamp: z.number(),
            flags: z.array(z.string()),
        }),
        z.discriminatedUnion("type", [
            z.object({
                type: z.literal("private"),
                topic_links: z.optional(z.array(z.undefined())),
            }),
            z.object({
                type: z.literal("stream"),
                stream_id: z.number(),
                // Messages that come from the server use `subject`.
                // Messages that come from `send_message` use `topic`.
                subject: z.optional(z.string()),
                topic: z.optional(z.string()),
                topic_links: z.array(topic_link_schema),
            }),
        ]),
    ),
    matched_message_schema,
);

export type RawMessage = z.infer<typeof raw_message_schema>;

// We add these boolean properties to Raw message in
// `message_store.convert_raw_message_to_message_with_booleans` method.
type Booleans = {
    unread: boolean;
    historical: boolean;
    starred: boolean;
    mentioned: boolean;
    mentioned_me_directly: boolean;
    stream_wildcard_mentioned: boolean;
    topic_wildcard_mentioned: boolean;
    collapsed: boolean;
    condensed?: boolean;
    alerted: boolean;
};

type RawMessageWithBooleans = (
    | Omit<RawMessage & {type: "private"}, "flags">
    | Omit<RawMessage & {type: "stream"}, "flags">
) &
    Booleans;

type LocalMessageWithBooleans = (
    | Omit<RawLocalMessage & {type: "private"}, "flags">
    | Omit<RawLocalMessage & {type: "stream"}, "flags">
) &
    Booleans;

export type MessageWithBooleans = RawMessageWithBooleans | LocalMessageWithBooleans;

export type MessageCleanReaction = {
    class: string;
    count: number;
    emoji_alt_code: boolean;
    emoji_code: string;
    emoji_name: string;
    is_realm_emoji: boolean;
    label: string;
    local_id: string;
    reaction_type: "zulip_extra_emoji" | "realm_emoji" | "unicode_emoji";
    user_ids: number[];
    vote_text: string;
};

export type Message = (
    | Omit<RawMessageWithBooleans & {type: "private"}, "reactions">
    | Omit<RawMessageWithBooleans & {type: "stream"}, "reactions" | "subject">
) & {
    clean_reactions: Map<string, MessageCleanReaction>;

    // Local echo state cluster of fields.
    locally_echoed?: boolean;
    failed_request?: boolean;
    show_slow_send_spinner?: boolean;
    resend?: boolean;
    local_id?: string;

    // The original markup for the message, which we'll have if we
    // sent it or if we fetched it (usually, because the current user
    // tried to edit the message).
    raw_content?: string | undefined;

    // Added in `message_helper.process_new_message`.
    sent_by_me: boolean;
    reply_to: string;

    // These properties are set and used in `message_list_view.ts`.
    // TODO: It would be nice if we could not store these on the message
    // object and only reference them within `message_list_view`.
    message_reactions?: MessageCleanReaction[];
    url?: string;

    // Used in `markdown.js`, `server_events.js`, and
    // `convert_raw_message_to_message_with_booleans`
    flags?: string[];

    // Used in `message_avatar.hbs` to render sender avatar in
    // message list.
    small_avatar_url?: string | null;

    // Used in `message_body.hbs` to show sender status emoji alongside
    // their name in message list.
    status_emoji_info?: UserStatusEmojiInfo | undefined;

    // Used for edited messages to show their last edit time.
    local_edit_timestamp?: number;

    // Used in message_notifications to track if a notification has already
    // been sent for this message.
    notification_sent?: boolean;

    // Added during message rendering in message_list_view.ts. Should
    // never be accessed outside rendering, as the value may be stale.
    reminders?: TimeFormattedReminder[] | undefined;
} & (
        | {
              type: "private";
              is_private: true;
              is_stream: false;
              pm_with_url: string;
              to_user_ids: string;
              display_reply_to: string;
          }
        | {
              type: "stream";
              is_private: false;
              is_stream: true;
              stream: string;
              topic: string;
              display_reply_to: undefined;
          }
    );

export function update_message_cache(message_data: ProcessedMessage): void {
    // You should only call this from message_helper (or in tests).
    stored_messages.set(message_data.message.id, message_data);
    remove_message_from_topic_links(message_data.message.id);
    save_topic_links(message_data.message);
}

export function get_cached_message(message_id: number): ProcessedMessage | undefined {
    // You should only call this from message_helper.
    // Use the get() wrapper below for most other use cases.
    return stored_messages.get(message_id);
}

export function clear_for_testing(): void {
    stored_messages.clear();
}

// This can return a LocalMessage, but unless anything needs that,
// it's easier to type it as just returning a Message.
// TODO: If we finish converting to typescript and find that
// nothing needs LocalMessage, explicitly remove its extra fields
// here before returning the Message.
export function get(message_id: number): Message | undefined {
    return stored_messages.get(message_id)?.message;
}

export function get_pm_emails(
    message: Message | MessageWithBooleans | LocalMessageWithBooleans,
): string {
    const user_ids = people.pm_with_user_ids(message) ?? [];
    const emails = user_ids.map((user_id) => {
        const person = people.maybe_get_user_by_id(user_id);
        if (!person) {
            blueslip.error("Unknown user id", {user_id});
            return "?";
        }
        return person.email;
    });
    emails.sort();

    return emails.join(", ");
}

export function get_pm_full_names(user_ids: number[]): string {
    user_ids = people.sorted_other_user_ids(user_ids);
    const sorted_names = people.get_display_full_names(user_ids);
    sorted_names.sort(util.make_strcmp());

    return sorted_names.join(", ");
}

export function convert_raw_message_to_message_with_booleans(opts: NewMessage):
    | {
          type: "server_message";
          message: RawMessageWithBooleans;
      }
    | {
          type: "local_message";
          message: LocalMessageWithBooleans;
      } {
    const flags = opts.raw_message.flags ?? [];

    function convert_flag(flag_name: string): boolean {
        return flags.includes(flag_name);
    }

    const converted_flags = {
        unread: !convert_flag("read"),
        historical: convert_flag("historical"),
        starred: convert_flag("starred"),
        mentioned:
            convert_flag("mentioned") ||
            convert_flag("stream_wildcard_mentioned") ||
            convert_flag("topic_wildcard_mentioned"),
        mentioned_me_directly: convert_flag("mentioned"),
        stream_wildcard_mentioned: convert_flag("stream_wildcard_mentioned"),
        topic_wildcard_mentioned: convert_flag("topic_wildcard_mentioned"),
        collapsed: convert_flag("collapsed"),
        alerted: convert_flag("has_alert_word"),
    };

    // Once we have set boolean flags here, the `flags` attribute is
    // just a distraction, so we delete it.  (All the downstream code
    // uses booleans.)

    // We have to return these separately because of how the `MessageWithBooleans`
    // type is set up.
    if (opts.type === "local_message") {
        if (opts.raw_message.type === "private") {
            return {
                type: "local_message",
                message: {
                    ..._.omit(opts.raw_message, "flags"),
                    ...converted_flags,
                },
            };
        }
        return {
            type: "local_message",
            message: {
                ..._.omit(opts.raw_message, "flags"),
                ...converted_flags,
            },
        };
    }
    if (opts.raw_message.type === "private") {
        return {
            type: "server_message",
            message: {
                ..._.omit(opts.raw_message, "flags"),
                ...converted_flags,
            },
        };
    }
    return {
        type: "server_message",
        message: {
            ..._.omit(opts.raw_message, "flags"),
            ...converted_flags,
        },
    };
}

export function update_booleans(message: Message, flags: string[]): void {
    // When we get server flags for local echo or message edits,
    // we are vulnerable to race conditions, so only update flags
    // that are driven by message content.
    function convert_flag(flag_name: string): boolean {
        return flags.includes(flag_name);
    }

    message.mentioned =
        convert_flag("mentioned") ||
        convert_flag("stream_wildcard_mentioned") ||
        convert_flag("topic_wildcard_mentioned");
    message.mentioned_me_directly = convert_flag("mentioned");
    message.stream_wildcard_mentioned = convert_flag("stream_wildcard_mentioned");
    message.topic_wildcard_mentioned = convert_flag("topic_wildcard_mentioned");
    message.alerted = convert_flag("has_alert_word");
}

export function update_sender_full_name(user_id: number, new_name: string): void {
    for (const message_data of stored_messages.values()) {
        const message = message_data.message;
        if (message.sender_id && message.sender_id === user_id) {
            message.sender_full_name = new_name;
        }
    }
}

export function update_small_avatar_url(user_id: number, new_url: string | null): void {
    for (const message_data of stored_messages.values()) {
        const message = message_data.message;
        if (message.sender_id && message.sender_id === user_id) {
            message.small_avatar_url = new_url;
        }
    }
}

export function update_stream_name(stream_id: number, new_name: string): void {
    for (const message_data of stored_messages.values()) {
        const message = message_data.message;
        if (message.type === "stream" && message.stream_id === stream_id) {
            message.display_recipient = new_name;
        }
    }
}

export function update_status_emoji_info(
    user_id: number,
    new_info: UserStatusEmojiInfo | undefined,
): void {
    for (const message_data of stored_messages.values()) {
        const message = message_data.message;
        if (message.sender_id && message.sender_id === user_id) {
            message.status_emoji_info = new_info;
        }
    }
}

export function reify_message_id({old_id, new_id}: {old_id: number; new_id: number}): void {
    const message_data = stored_messages.get(old_id);
    if (message_data !== undefined) {
        const server_message: Message & Partial<LocalMessage> = message_data.message;
        if (message_data.type === "local_message") {
            // Important: Messages are managed as singletons, so
            // MessageListData objects may already have pointers to
            // the LocalMessage object for this message. So we must
            // convert the LocalMessage into a Message by dropping the
            // extra local echo/drafts fields, not by constructing a
            // new object with the new type.

            delete server_message.queue_id;
            delete server_message.draft_id;
            delete server_message.to;
            if (server_message.type === "private") {
                delete server_message.topic;
            }
        }
        if (server_message.type === "stream") {
            update_message_id_in_topic_links(old_id, new_id);
        }
        server_message.id = new_id;
        server_message.locally_echoed = false;
        stored_messages.set(new_id, {type: "server_message", message: server_message});
        stored_messages.delete(old_id);
    }
}

// A link in a message, possibly to just a stream (undefined topic)
// possibly to a stream>topic, and possibly to a message in a
// stream>topic
export type TopicLink = {
    stream_id: number;
    topic: string | undefined;
    message_id: number | undefined;
};

const NO_MESSAGE_ID = 0;

function get_or_create_link_map_for_narrow<T>(
    map: Map<number, Map<string, Map<number, T[]>>>,
    stream_id: number,
    topic: string,
): Map<number, T[]> {
    if (!map.has(stream_id)) {
        map.set(stream_id, new Map<string, Map<number, T[]>>());
    }
    if (!map.get(stream_id)!.get(topic)) {
        map.get(stream_id)!.set(topic, new Map<number, T[]>());
    }
    return map.get(stream_id)!.get(topic)!;
}

// from_stream_id -> from_topic -> from_message_id -> TopicLink[]
const topic_links_by_from = new Map<number, Map<string, Map<number, TopicLink[]>>>();
export function topic_links_by_from_for_testing(): Map<
    number,
    Map<string, Map<number, TopicLink[]>>
> {
    return topic_links_by_from;
}

// to_stream_id -> to_topic -> to_message_id -> from_message_id[]
// Instead of storing a TopicLink, this only stores the from_message_id
// since we can get that message's narrow data from its id.
const topic_links_by_to = new Map<number, Map<string, Map<number, number[]>>>();
export function topic_links_by_to_for_testing(): Map<number, Map<string, Map<number, number[]>>> {
    return topic_links_by_to;
}

export function clear_topic_links_for_testing(): void {
    topic_links_by_from.clear();
    topic_links_by_to.clear();
}

export function topic_links_from_narrow(
    stream_id: number,
    topic: string,
): {
    text: string;
    url: string;
}[] {
    const narrow_map = topic_links_by_from.get(stream_id)?.get(topic);
    if (narrow_map === undefined) {
        return [];
    }

    // `topic_links_by_from` stores messages by the order they're inserted,
    // which is the order they're fetched from the server, which isn't necessarily
    // by most recent, e.g. if a user fetches scrolls back in a conversation to
    // load more messages. So now we sort them, but we can sort by ID instead of
    // timestamp since messages are sorted temporally by ID.
    const messages_with_links = [...narrow_map.keys()].toSorted((a, b) => a - b);

    const links_from_narrow: TopicLink[] = [];
    // We keep a set of links for deduplication, and stringify the links because
    // sets of objects won't work due to the way object equality works in JavaScript.
    const added_links = new Set<string>();

    for (const message_id of messages_with_links) {
        for (const link of narrow_map.get(message_id)!) {
            // Hide links from this topic to the same topic, if they're not pointing to
            // a specific message, since those feel unnecessary to reference.
            if (
                link.stream_id === stream_id &&
                link.topic === topic &&
                link.message_id === undefined
            ) {
                continue;
            }
            const link_string = JSON.stringify(link);
            if (added_links.has(link_string)) {
                continue;
            }
            added_links.add(link_string);
            links_from_narrow.push(link);
        }
    }

    return links_from_narrow.map((topic_link) => {
        if (topic_link.message_id !== undefined) {
            const message = get(topic_link.message_id);
            assert(message?.type === "stream");
            return topic_link_util.get_topic_link_content_with_stream_id({
                stream_id: message.stream_id,
                topic_name: message.topic,
                message_id: message.id.toString(),
                escape_for_markdown: false,
            });
        }
        return topic_link_util.get_topic_link_content_with_stream_id({
            stream_id: topic_link.stream_id,
            topic_name: topic_link.topic,
            message_id: undefined,
            escape_for_markdown: false,
        });
    });
}

export function topic_links_to_narrow(
    stream_id: number,
    topic: string,
): {
    text: string;
    url: string;
}[] {
    const narrow_map = topic_links_by_to.get(stream_id)?.get(topic);
    if (narrow_map === undefined) {
        return [];
    }

    // `topic_links_by_to` stores messages by the order they're inserted,
    // which is the order they're fetched from the server, which isn't necessarily
    // by most recent, e.g. if a user fetches scrolls back in a conversation to
    // load more messages. So now we sort them, but we can sort by ID instead of
    // timestamp since messages are sorted temporally by ID.
    const messages_linking_to_narrow = [...narrow_map.values()].flat().toSorted((a, b) => a - b);

    const topic_links_content = [];
    // We keep a set of stream/topic data for deduplication, since we only want to show
    // one link per narrow that links to this narrow. We use the first message that does
    // so, and discard all following messages from the same narrow. We have to stringify
    // the stream/topic data because sets of objects won't work due to the way object
    // equality works in JavaScript.
    const added_narrows = new Set<string>();

    for (const from_message_id of messages_linking_to_narrow) {
        const message = get(from_message_id);
        assert(message?.type === "stream");
        // Hide links to this topic from the same topic, since those feel
        // unnecessary to reference.
        if (message.stream_id === stream_id && message.topic === topic) {
            continue;
        }
        const stream_topic = JSON.stringify({stream_id: message.stream_id, topic: message.topic});
        if (added_narrows.has(stream_topic)) {
            continue;
        }
        added_narrows.add(stream_topic);
        topic_links_content.push(
            topic_link_util.get_topic_link_content_with_stream_id({
                stream_id: message.stream_id,
                topic_name: message.topic,
                message_id: message.id.toString(),
                escape_for_markdown: false,
            }),
        );
    }
    return topic_links_content;
}

// If new_message_id = undefined, the message has been deleted, so remove
// all references to it. Otherwise update our maps to store the new message id.
// If updating, this must be called while the message object still has the
// old message id, so that we can fetch it from the message store.
function _remove_or_update_message_id_from_topic_links(
    old_message_id: number,
    new_message_id: number | undefined,
): void {
    assert(old_message_id !== NO_MESSAGE_ID);
    assert(new_message_id !== NO_MESSAGE_ID);
    const updated_message = get(old_message_id);
    if (updated_message?.type !== "stream") {
        return;
    }

    const {stream_id, topic} = updated_message;

    // (1) Update any record of links to this message.
    const links_to_narrow = topic_links_by_to.get(stream_id)?.get(topic);
    if (links_to_narrow?.has(old_message_id)) {
        // (1a) Update records in `topic_links_by_to` for messages pointing to the message
        // we're updating.
        const messages_linking_to_updated_message = links_to_narrow.get(old_message_id)!;
        links_to_narrow.delete(old_message_id);
        // If we're updating the message id, save this data under the new message id.
        if (new_message_id) {
            links_to_narrow.set(
                new_message_id,
                // Handle edge case where messages_linking_to_updated_message contains
                // the old_message_id - we need to update it to be the new_message_id.
                messages_linking_to_updated_message.map((message_id) =>
                    message_id === old_message_id ? new_message_id : message_id,
                ),
            );
        }

        // (1b) Update/delete the matching links in `topic_links_by_from`
        // i.e. links from messages to this updated message, since they need
        // to point to the correct new message id.
        for (const message_id of messages_linking_to_updated_message) {
            const message = get(message_id);
            assert(message?.type === "stream");
            const links = topic_links_by_from
                .get(message.stream_id)!
                .get(message.topic)!
                .get(message.id)!;
            if (new_message_id) {
                for (const link of links) {
                    if (link.message_id === old_message_id) {
                        link.message_id = new_message_id;
                    }
                }
            } else {
                // An undefined new_message_id means we're deleting the old message id
                // from the links.
                const filtered_links = links.filter(
                    (topic_link) => topic_link.message_id !== old_message_id,
                );
                topic_links_by_from
                    .get(message.stream_id)!
                    .get(message.topic)!
                    .set(message_id, filtered_links);
            }
        }
    }

    // (2) Update links from this message to other streams/topics/messages.
    const links_from_narrow = topic_links_by_from.get(stream_id)?.get(topic);
    if (links_from_narrow?.has(old_message_id)) {
        // (2a) Update records in `topic_links_by_from` from message we're updating.
        const messages_linked_from_updated_message = links_from_narrow.get(old_message_id)!;
        links_from_narrow.delete(old_message_id);
        if (new_message_id) {
            links_from_narrow.set(new_message_id, messages_linked_from_updated_message);
        }

        // (2b) Delete matching records in `topic_links_by_to`,
        // i.e. links to messages from this updated message, since they need
        // to store correct new message id.
        for (const link of messages_linked_from_updated_message) {
            // If there's no topic we're linking to, it won't be in the
            // `topic_links_by_to` map.
            if (!link.topic) {
                continue;
            }
            // If there's no specified `to_message_id`, it was a link to a topic
            // but not a specific message. That uses `NO_MESSAGE_ID`.
            const to_message_id = link.message_id ?? NO_MESSAGE_ID;
            const link_map = topic_links_by_to.get(link.stream_id)?.get(link.topic);
            if (link_map?.has(to_message_id)) {
                const links_to_message = link_map.get(to_message_id)!;
                if (new_message_id) {
                    links_to_message.push(new_message_id);
                }
                link_map.set(
                    to_message_id,
                    links_to_message.filter((message_id) => message_id !== old_message_id),
                );
            }
        }
    }
}

function update_message_id_in_topic_links(old_message_id: number, new_message_id: number): void {
    _remove_or_update_message_id_from_topic_links(old_message_id, new_message_id);
}

function remove_message_from_topic_links(message_id: number): void {
    _remove_or_update_message_id_from_topic_links(message_id, undefined);
}

export let save_topic_links = (message: Message): void => {
    if (message.type !== "stream") {
        return;
    }
    if (muted_users.is_user_muted(message.sender_id)) {
        return;
    }

    // Extract the URLs from the message content. It's unfortunate that this will
    // result in the web app parsing the HTML for the message an additional time
    // just for this feature, but there doesn't seem to be a nicer way to do it.
    for (const link of [...$(message.content).find("a")].map((link) => link.href)) {
        const hash = hash_util.get_link_hash(link);
        if (!hash.startsWith("#narrow/")) {
            continue;
        }
        const link_data = hash_util.decode_stream_topic_from_url(hash, false);
        if (link_data === null) {
            continue;
        }

        const to_stream_id = link_data.stream_id;
        const to_topic = link_data.topic_name;
        const to_message_id = link_data.message_id
            ? Number.parseInt(link_data.message_id, 10)
            : undefined;

        // If we don't have access to this stream and/or message, or it's a buggy link,
        // or it's a message from a muted user, just ignore it.
        if (!stream_data.get_sub_by_id(to_stream_id)) {
            continue;
        }
        if (to_message_id !== undefined) {
            const to_message = get(to_message_id);
            if (to_message === undefined) {
                continue;
            }
            if (muted_users.is_user_muted(to_message.sender_id)) {
                continue;
            }
        }

        // (1) Save link in topic_links_by_from
        const topic_links_from_message_narrow = get_or_create_link_map_for_narrow(
            topic_links_by_from,
            message.stream_id,
            message.topic,
        );
        const topic_links_from_message = topic_links_from_message_narrow.get(message.id) ?? [];
        // Note: This is O(# of links for message_id)
        util.unique_array_insert(topic_links_from_message, {
            stream_id: to_stream_id,
            topic: to_topic,
            message_id: to_message_id,
        });
        topic_links_from_message_narrow.set(message.id, topic_links_from_message);

        // (2) Update topic_links_by_to, if relevant
        if (to_topic === undefined) {
            continue;
        }
        const topic_links_to_message_narrow = get_or_create_link_map_for_narrow(
            topic_links_by_to,
            to_stream_id,
            to_topic,
        );
        const topic_links_to_message =
            topic_links_to_message_narrow.get(to_message_id ?? NO_MESSAGE_ID) ?? [];
        // Note: This is O(# of links for message_id, which could be a lot for NO_MESSAGE_ID)
        util.unique_array_insert(topic_links_to_message, message.id);
        topic_links_to_message_narrow.set(to_message_id ?? NO_MESSAGE_ID, topic_links_to_message);
    }
};

export function rewire_save_topic_links(value: typeof save_topic_links): void {
    save_topic_links = value;
}

// Important: Messages should still have the old stream and topic when this
// function is called, so that we can fetch their old records in the link maps.
export function process_topic_edit(opts: {
    message_ids: number[];
    new_stream_id: number;
    new_topic: string;
}): void {
    const {message_ids, new_stream_id, new_topic} = opts;
    for (const message_id of message_ids) {
        const message = get(message_id);
        assert(message?.type === "stream");
        const old_stream_id = message.stream_id;
        const old_topic = message.topic;

        // Move any links from this message stored with the old topic
        const links_from_old_narrow = topic_links_by_from.get(old_stream_id)?.get(old_topic);
        const links_from_edited_message = links_from_old_narrow?.get(message_id);
        if (links_from_edited_message !== undefined) {
            const new_narrow_link_map = get_or_create_link_map_for_narrow(
                topic_links_by_from,
                new_stream_id,
                new_topic,
            );
            new_narrow_link_map.set(message_id, links_from_edited_message);
            links_from_old_narrow!.delete(message_id);
        }

        // Move any links to this message stored with the old topic
        const links_to_old_narrow = topic_links_by_to.get(old_stream_id)?.get(old_topic);
        const links_to_edited_message = links_to_old_narrow?.get(message_id);
        if (links_to_edited_message !== undefined) {
            const new_narrow_link_map = get_or_create_link_map_for_narrow(
                topic_links_by_to,
                new_stream_id,
                new_topic,
            );
            new_narrow_link_map.set(message_id, links_to_edited_message);
            links_to_old_narrow!.delete(message_id);
        }
    }
}

export function update_message_content(
    message: Message,
    new_content: string,
    may_have_updated_links = true,
): void {
    message.content = new_content;

    // DM messages aren't currently part of cross-conversation links.
    // TODO: Consider adding this in the future.
    if (message.type !== "stream" || !may_have_updated_links) {
        return;
    }
    // The content might have a different set of message links, so reparse
    // the content and update the map. A prior check to see if anything
    // changed takes a comparable amount of time (recalculating the topic
    // links, and sorting them to compare to current links), so it's easier
    // to just wipe the data and recalculate.
    remove_message_from_topic_links(message.id);
    save_topic_links(message);
}

export function remove(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = get(message_id);
        if (message?.type === "stream") {
            remove_message_from_topic_links(message.id);
        }
        stored_messages.delete(message_id);
    }
}

export function get_message_ids_in_stream(stream_id: number): number[] {
    return [...stored_messages.values()]
        .filter(
            (message_data) =>
                message_data.message.type === "stream" &&
                message_data.message.stream_id === stream_id,
        )
        .map((message_data) => message_data.message.id);
}
