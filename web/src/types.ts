// TODO/typescript: Move this to message_store
export type MatchedMessage = {
    match_content?: string;
    match_subject?: string;
};

// TODO/typescript: Move this to message_store
export type MessageType = "private" | "stream";
export type MessageReactionType = "unicode_emoji" | "realm_emoji" | "zulip_extra_emoji";

// TODO/typescript: Move these types to message_store

export type DisplayRecipientUser = {
    email: string;
    full_name: string;
    id: number;
    is_mirror_dummy: boolean;
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

// TODO/typescript: Move this to server_events
export type TopicLink = {
    text: string;
    url: string;
};

// TODO/typescript: Move this to message_store
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
    stream_id?: number;
    subject: string;
    submessages: string[];
    timestamp: number;
    topic_links: TopicLink[];
    type: MessageType;
    flags: string[];
} & MatchedMessage;

// TODO/typescript: Move this to message_store
export type Message = RawMessage & {
    to_user_ids?: string;
    topic: string;
};

// TODO/typescript: Move this to server_events_dispatch
export type UserGroupUpdateEvent = {
    id: number;
    type: string;
    group_id: number;
    data: {
        name?: string;
        description?: string;
    };
};

// TODO/typescript: Move this to server_events
export type UpdateMessageEvent = {
    id: number;
    type: string;
    user_id: number | null;
    rendering_only: boolean;
    message_id: number;
    message_ids: number[];
    flags: string[];
    edit_timestamp: number;
    stream_name?: string;
    stream_id?: number;
    new_stream_id?: number;
    propagate_mode?: string;
    orig_subject?: string;
    subject?: string;
    topic_links?: TopicLink[];
    orig_content?: string;
    orig_rendered_content?: string;
    prev_rendered_content_version?: number;
    content?: string;
    rendered_content?: string;
    is_me_message?: boolean;
    // The server is still using subject.
    // This will not be set until it gets fixed.
    topic?: string;
};

// TODO/typescript: Move the User and Stream placeholder
// types to their appropriate modules.
export type User = Record<string, never>;

// TODO/typescript: Move this to channel
export type AjaxRequestHandler = (args: {
    url: string;
    data?: Record<string, unknown> | string | unknown[];
    ignoreReload?: boolean;
    success?(response_data: unknown, textStatus: string, jqXHR: JQuery.jqXHR): void;
    error?(xhr: JQuery.jqXHR, error_type: string, xhn: string): void;
}) => void;
