interface Message {
    id: number;
    sender_id: number;
    content: string;
    recipient_id: number;
    timestamp: number;
    client: string;
    topic_links: string[];
    is_me_message: boolean;
    reactions: unknown[];
    submessages: unknown[];
    sender_full_name: string;
    sender_short_name: string;
    sender_email: string;
    sender_realm_str: string;
    display_recipient: string | unknown[];
    type: string;
    avatar_url: string;
    content_type: string;
    unread: boolean;
    historical: boolean;
    starred: boolean;
    mentioned: boolean;
    mentioned_me_directly: boolean;
    collapsed: boolean;
    alerted: boolean;
    sent_by_me: boolean;
    topic: string;
    is_stream: boolean;
    stream: string;
    reply_to: string;
    starred_status: string;
    clean_reactions: Map<string, unknown>;
    message_reactions: unknown[];

    match_data?: string;
    match_topic?: string;
    match_subject?: string;
    match_content?: string;

    // stream_id is not present in Group or Private PM message.
    stream_id?: number;

    // Subject is always present, as of now, but we mark it optional
    // because we intent to remove it in favor of topic eventually.
    subject?: string;

    // Set in timerender.js for some messages only
    full_date_str?: string;
    full_time_str?: string;

    // Only set for private messages
    pm_with_url?: string;
    to_user_ids?: string;
}
