// TODO: Move this to message_store when it is
// converted to TypeScript.
interface BaseMessage {
    content: string;
    match_content?: string;
    match_subject?: string;
    sender_email: string;
}

export interface PrivateMessage extends BaseMessage {
    type: "private";
    to_user_ids: string;
}

export interface StreamMessage extends BaseMessage {
    type: "stream";
    stream_id: number;
    subject: string;
    topic?: string;
}

export type Message = PrivateMessage | StreamMessage;

// TODO: Move the UpdateMessageEvent to server_events
// when it is converted to TypeScript.
export interface UpdateMessageEvent {
    orig_subject?: string;
    prev_subject?: string;
    subject: string;
    topic?: string;
}
