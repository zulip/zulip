// TODO/typescript: Move this to message_store
export type MatchedMessage = {
    match_content?: string;
    match_subject?: string;
};

// TODO/typescript: Move this to message_store
export type MessageType = "private" | "stream";

// TODO/typescript: Move this to message_store
export type RawMessage = {
    sender_email: string;
    stream_id: number;
    subject: string;
    type: MessageType;
} & MatchedMessage;

// TODO/typescript: Move this to message_store
export type Message = RawMessage & {
    to_user_ids: string;
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
export type TopicLink = {
    text: string;
    url: string;
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
