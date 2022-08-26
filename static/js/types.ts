export type MessageType = "private" | "stream";

export type RawMessage = {
    sender_email: string;
    stream_id: number;
    type: MessageType;
};

export type Message = RawMessage & {
    match_content: string;
    match_subject: string;
    orig_subject: string;
    subject: string;
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

// TODO/typescript: Move the User and Stream placeholder
// types to their appropriate modules.
export type User = Record<string, never>;
