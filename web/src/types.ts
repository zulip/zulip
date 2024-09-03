import {z} from "zod";

// TODO/typescript: Move this to server_events
export const topic_link_schema = z.object({
    text: z.string(),
    url: z.string(),
});

export type TopicLink = z.infer<typeof topic_link_schema>;

// TODO/typescript: Move this to server_events_dispatch
export type UserGroupUpdateEvent = {
    id: number;
    type: string;
    group_id: number;
    data: {
        name?: string;
        description?: string;
        can_manage_group?: number;
        can_mention_group?: number;
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
    content?: string;
    rendered_content?: string;
    is_me_message?: boolean;
    // The server is still using subject.
    // This will not be set until it gets fixed.
    topic?: string;
};

export type HTMLSelectOneElement = HTMLSelectElement & {type: "select-one"};
