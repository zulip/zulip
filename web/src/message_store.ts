import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import type {EmojiRenderingDetails} from "./emoji";
import * as people from "./people";
import type {Submessage, TopicLink} from "./types";

export type MatchedMessage = {
    match_content?: string;
    match_subject?: string;
};

export type MessageReactionType = "unicode_emoji" | "realm_emoji" | "zulip_extra_emoji";

export type DisplayRecipientUser = {
    email: string;
    full_name: string;
    id: number;
    is_mirror_dummy: boolean;
    unknown_local_echo_user?: boolean;
};

export type DisplayRecipient = string | DisplayRecipientUser[];

export type MessageEditHistoryEntry = {
    user_id: number | null;
    timestamp: number;
    prev_content?: string;
    prev_rendered_content?: string;
    prev_rendered_content_version?: number;
    prev_stream?: number;
    prev_topic?: string;
    stream?: number;
    topic?: string;
};

export type MessageReaction = {
    emoji_name: string;
    emoji_code: string;
    reaction_type: MessageReactionType;
    user_id: number;
};

export type RawMessage = {
    avatar_url: string | null;
    client: string;
    content: string;
    content_type: "text/html";
    display_recipient: DisplayRecipient;
    edit_history?: MessageEditHistoryEntry[];
    id: number;
    is_me_message: boolean;
    last_edit_timestamp?: number;
    reactions: MessageReaction[];
    recipient_id: number;
    sender_email: string;
    sender_full_name: string;
    sender_id: number;
    sender_realm_str: string;
    submessages: Submessage[];
    timestamp: number;
    flags: string[];
} & (
    | {
          type: "private";
      }
    | {
          type: "stream";
          stream_id: number;
          subject: string;
          topic_links: TopicLink[];
      }
) &
    MatchedMessage;

export type MessageWithBooleans = (
    | Omit<RawMessage & {type: "private"}, "flags">
    | Omit<RawMessage & {type: "stream"}, "flags">
) & {
    unread: boolean;
    historical: boolean;
    starred: boolean;
    mentioned: boolean;
    mentioned_me_directly: boolean;
    stream_wildcard_mentioned: boolean;
    topic_wildcard_mentioned: boolean;
    collapsed: boolean;
    alerted: boolean;
};

export type MessageCleanReaction = {
    class: string;
    count: number;
    emoji_alt_code: boolean;
    emoji_code: string;
    emoji_name: string;
    is_realm_emoji: boolean;
    label: string;
    local_id: string;
    reaction_type: string;
    user_ids: number[];
    vote_text: string;
};

export type Message = (
    | Omit<MessageWithBooleans & {type: "private"}, "reactions">
    | Omit<MessageWithBooleans & {type: "stream"}, "reactions">
) & {
    // Added in `reactions.set_clean_reactions`.
    clean_reactions: Map<string, MessageCleanReaction>;

    // Added in `message_helper.process_new_message`.
    sent_by_me: boolean;
    reply_to: string;
    display_reply_to?: string;

    // These properties are used in `message_list_view.js`.
    starred_status: string;
    message_reactions: MessageCleanReaction[];
    url: string;

    status_emoji_info: EmojiRenderingDetails;
    small_avatar_url: string | null;
} & (
        | {
              type: "private";
              is_private: true;
              is_stream: false;
              pm_with_url: string;
              to_user_ids: string;
          }
        | {
              type: "stream";
              is_private: false;
              is_stream: true;
              stream: string;
              topic: string;
          }
    );

const stored_messages = new Map<number, Message>();

export function update_message_cache(message: Message): void {
    // You should only call this from message_helper (or in tests).
    stored_messages.set(message.id, message);
}

export function get_cached_message(message_id: number): Message | undefined {
    // You should only call this from message_helper.
    // Use the get() wrapper below for most other use cases.
    return stored_messages.get(message_id);
}

export function clear_for_testing(): void {
    stored_messages.clear();
}

export function get(message_id: number): Message | undefined {
    if (message_id === undefined || message_id === null) {
        blueslip.error("message_store.get got bad value", {message_id});
        return undefined;
    }

    if (typeof message_id !== "number") {
        blueslip.error("message_store got non-number", {message_id});

        // Try to soldier on, assuming the caller treats message
        // ids as strings.
        message_id = Number.parseFloat(message_id);
    }

    return stored_messages.get(message_id);
}

export function get_pm_emails(message: Message & {reply_to?: string; url?: string}): string {
    const user_ids = people.pm_with_user_ids(message);
    assert(user_ids !== undefined, "user_ids is undefined");
    const emails = user_ids
        .map((user_id) => {
            const person = people.maybe_get_user_by_id(user_id);
            if (!person) {
                blueslip.error("Unknown user id", {user_id});
                return "?";
            }
            return person.email;
        })
        .sort();

    return emails.join(", ");
}

export function get_pm_full_names(message: Message & {reply_to?: string; url?: string}): string {
    const user_ids = people.pm_with_user_ids(message);
    assert(user_ids !== undefined, "user_ids is undefined");
    const names = people.get_display_full_names(user_ids).sort();

    return names.join(", ");
}

export function set_message_booleans(raw_message: RawMessage): MessageWithBooleans {
    const {flags, ...raw_message_without_flags} = raw_message;

    function convert_flag(flag_name: string): boolean {
        return flags.includes(flag_name);
    }

    const message: MessageWithBooleans = {
        ...raw_message_without_flags,
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
    return message;
}

export function update_booleans(message: MessageWithBooleans, flags: string[]): void {
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

export function update_stream_name(value: string, info: {stream_id: number}): void {
    for (const msg of stored_messages.values()) {
        if (msg.type === "stream" && msg.stream_id === info.stream_id) {
            msg.display_recipient = value;
        }
    }
}

export function update_status_emoji_info(
    value: EmojiRenderingDetails,
    info: {user_id: number},
): void {
    for (const msg of stored_messages.values()) {
        if (msg.sender_id && msg.sender_id === info.user_id) {
            msg.status_emoji_info = value;
        }
    }
}

export function update_sender_full_name(value: string, info: {user_id: number}): void {
    for (const msg of stored_messages.values()) {
        if (msg.sender_id && msg.sender_id === info.user_id) {
            msg.sender_full_name = value;
        }
    }
}

export function update_small_avatar_url(value: string, info: {user_id: number}): void {
    for (const msg of stored_messages.values()) {
        if (msg.sender_id && msg.sender_id === info.user_id) {
            msg.small_avatar_url = value;
        }
    }
}

export function reify_message_id({old_id, new_id}: {old_id: number; new_id: number}): void {
    if (stored_messages.has(old_id)) {
        stored_messages.set(new_id, stored_messages.get(old_id)!);
        stored_messages.delete(old_id);
    }
}