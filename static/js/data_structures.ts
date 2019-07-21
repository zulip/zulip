import { Dict } from './dict';

export interface Recipient {
    email: string;
    full_name: string;
    id: number;
    user_id?: number;
    is_mirror_dummy: boolean;
    short_name: string;
    unknown_local_echo_user?: true;
}
export interface FakePerson {
    email: string;
    full_name: string;
    pm_recipient_count: number;  /** Infinity */
    special_item_text: string;
}
export interface BaseReaction {
    emoji_code: string;
    emoji_name: string;
    local_id: string;
    reaction_type: string;
    user_ids: number[];
}
export interface MessageReaction extends BaseReaction {
    class: string;
    count: number;
    emoji_alt_code: boolean;
    title: string;
}
export interface Reaction extends BaseReaction {
    user: {
        email: string;
        full_name: string;
        id: number;
    };
}
export interface Message {
    alerted: boolean;
    avatar_url: string | null;
    client: string;
    collapsed: boolean;
    content: string;
    content_type: string;
    display_recipient: Recipient[];
    display_reply_to: string;
    historical: boolean;
    id: number;
    is_me_message: boolean;
    is_private: boolean;
    mentioned: boolean;
    mentioned_me_directly: boolean;
    message_reactions: MessageReaction[];
    pm_with_url: string;
    reactions: Reaction[];
    recipient_id: number;
    reply_to: string;
    sender_email: string;
    sender_full_name: string;
    sender_id: number;
    sender_realm_str: string;
    sender_short_name: string;
    sent_by_me: boolean;
    starred: boolean;
    starred_status: string;
    stream_id?: number;
    subject: string;
    subject_links: string[];
    submessages: {
        id: number;
        sender_id: number;
        content: string;
    }[];
    timestamp: number;
    to_user_ids: string;
    topic: string;
    type: string;
    unread: boolean;
}

export interface Subscription {
    audible_notifications?: boolean;
    audible_notifications_display: boolean;
    can_access_subscribers: boolean;
    can_add_subscribers: boolean;
    can_change_name_description: boolean;
    can_change_stream_permissions: boolean;
    color: string;
    description: string;
    desktop_notifications?: boolean;
    desktop_notifications_display: boolean;
    email_address: string;
    email_notifications?: boolean;
    email_notifications_display: boolean;
    first_message_id: number;
    history_public_to_subscribers: boolean;
    in_home_view: boolean;
    invite_only: boolean;
    is_admin: boolean;
    is_announcement_only: boolean;
    is_muted: boolean;
    is_old_stream: boolean;
    is_web_public: boolean;
    name: string;
    newly_subscribed: boolean;
    pin_to_top: boolean;
    preview_url: string;
    previously_subscribed: boolean;
    push_notifications?: boolean;
    push_notifications_display: boolean;
    render_subscribers: boolean;
    rendered_description: string;
    should_display_preview_button: boolean;
    should_display_subscription_button: boolean;
    stream_id: number;
    stream_weekly_traffic?: number;
    subscribed: boolean;
    subscriber_count: number;
    subscribers: Dict<number, true>;
}
