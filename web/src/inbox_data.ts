import {user_settings} from "./user_settings.ts";
import type * as user_topics from "./user_topics.ts";

export const COLUMNS = {
    FULL_ROW: 0,
    UNREAD_COUNT: 1,
    TOPIC_VISIBILITY: 2,
    ACTION_MENU: 3,
};

export const OTHER_CHANNELS_FOLDER_ID = -1;
export const OTHER_CHANNEL_HEADER_ID = "inbox-channels-no-folder-header";
export const CHANNEL_FOLDER_HEADER_ID_PREFIX = "inbox-channel-folder-header-";
export const PINNED_CHANNEL_FOLDER_ID = -2;
export const PINNED_CHANNEL_HEADER_ID = "inbox-channels-pinned-folder-header";

export const STREAM_HEADER_PREFIX = "inbox-stream-header-";
export const CONVERSATION_ID_PREFIX = "inbox-row-conversation-";

export type DirectMessageContext = {
    conversation_key: string;
    is_direct: boolean;
    rendered_dm_with_html: string;
    is_group: boolean;
    user_circle_class: string | false | undefined;
    is_bot: boolean;
    dm_url: string;
    user_ids_string: string;
    unread_count: number;
    is_hidden: boolean;
    is_collapsed: boolean;
    latest_msg_id: number;
    column_indexes: typeof COLUMNS;
    has_unread_mention: boolean;
};

export const direct_message_context_properties: (keyof DirectMessageContext)[] = [
    "conversation_key",
    "is_direct",
    "rendered_dm_with_html",
    "is_group",
    "user_circle_class",
    "is_bot",
    "dm_url",
    "user_ids_string",
    "unread_count",
    "is_hidden",
    "is_collapsed",
    "latest_msg_id",
    "column_indexes",
];

export type StreamContext = {
    is_stream: boolean;
    is_archived: boolean;
    invite_only: boolean;
    is_web_public: boolean;
    stream_name: string;
    pin_to_top: boolean;
    is_muted: boolean;
    stream_color: string;
    stream_header_color: string;
    stream_url: string;
    stream_id: number;
    is_hidden: boolean;
    is_collapsed: boolean;
    mention_in_unread: boolean;
    unread_count?: number;
    column_indexes: typeof COLUMNS;
    folder_id: number;
};

export const stream_context_properties: (keyof StreamContext)[] = [
    "is_stream",
    "invite_only",
    "is_web_public",
    "stream_name",
    "pin_to_top",
    "is_muted",
    "stream_color",
    "stream_header_color",
    "stream_url",
    "stream_id",
    "is_hidden",
    "is_collapsed",
    "mention_in_unread",
    "unread_count",
    "column_indexes",
];

export type TopicContext = {
    is_topic: boolean;
    stream_id: number;
    stream_archived: boolean;
    topic_name: string;
    topic_display_name: string;
    is_empty_string_topic: boolean;
    unread_count: number;
    conversation_key: string;
    topic_url: string;
    is_hidden: boolean;
    is_collapsed: boolean;
    mention_in_unread: boolean;
    latest_msg_id: number;
    all_visibility_policies: typeof user_topics.all_visibility_policies;
    visibility_policy: number | false;
    column_indexes: typeof COLUMNS;
    channel_folder_id?: number;
};

export const topic_context_properties: (keyof TopicContext)[] = [
    "is_topic",
    "stream_id",
    "stream_archived",
    "topic_name",
    "topic_display_name",
    "is_empty_string_topic",
    "unread_count",
    "conversation_key",
    "topic_url",
    "is_hidden",
    "is_collapsed",
    "mention_in_unread",
    "latest_msg_id",
    "all_visibility_policies",
    "visibility_policy",
    "column_indexes",
    "channel_folder_id",
];

export type ChannelFolderContext = {
    header_id: string;
    is_header_visible: boolean;
    name: string;
    id: number;
    unread_count: number | undefined;
    is_collapsed: boolean;
    has_unread_mention: boolean;
    order: number;
};

export type FolderStreamRowsContext = {
    stream_key: string;
    stream_row: StreamContext;
    topic_rows: TopicContext[];
};

export const channel_folder_context_properties: (keyof ChannelFolderContext)[] = [
    "header_id",
    "is_header_visible",
    "name",
    "id",
    "unread_count",
    "is_collapsed",
    "has_unread_mention",
];

export function get_topic_key(stream_id: number, topic: string): string {
    // Topic names are case-preserving for display, but case insensitive
    // otherwise. We convert the topic key to lowercase to ensure that
    // topic keys with different casing are not treated differently.
    return stream_id + ":" + topic.toLowerCase();
}

export function get_stream_key(stream_id: number): string {
    return "stream_" + stream_id;
}

export function get_channel_folder_id(info: {
    folder_id: number | null;
    is_pinned: boolean;
}): number {
    if (info.is_pinned) {
        return PINNED_CHANNEL_FOLDER_ID;
    }
    if (info.folder_id === null) {
        return OTHER_CHANNELS_FOLDER_ID;
    }
    if (!user_settings.web_inbox_show_channel_folders) {
        return OTHER_CHANNELS_FOLDER_ID;
    }
    return info.folder_id;
}

export function get_channel_folder_header_id(folder_id: number): string {
    if (folder_id === OTHER_CHANNELS_FOLDER_ID) {
        return OTHER_CHANNEL_HEADER_ID;
    } else if (folder_id === PINNED_CHANNEL_FOLDER_ID) {
        return PINNED_CHANNEL_HEADER_ID;
    }
    return CHANNEL_FOLDER_HEADER_ID_PREFIX + folder_id;
}
