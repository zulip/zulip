import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import {$t} from "./i18n.ts";
import * as message_helper from "./message_helper.ts";
import * as message_notification from "./message_notifications.ts";
import * as message_store from "./message_store.ts";
import {raw_message_schema} from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as muted_users from "./muted_users.ts";
import * as people from "./people.ts";
import type {ReactionEvent} from "./reactions.ts";
import {current_user} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as ui_util from "./ui_util.ts";
import * as unread_ops from "./unread_ops.ts";
import {user_settings} from "./user_settings.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

const fetch_message_response_schema = z.object({
    message: raw_message_schema,
});

type ReactionEmojiDetail = Pick<ReactionEvent, "emoji_name" | "emoji_code" | "reaction_type">;

type NotifiedReaction = {
    user_id: number;
    emoji_detail: ReactionEmojiDetail;
};

// For each message with a live reaction notification (keyed by message
// id), its individual notified reactions, keyed by reaction_identity_key
// and ordered by arrival, so the notification title can render the newest
// reactions and reactors first, and so a single reaction can be removed
// precisely when the reacting user unreacts.
const message_reactions = new Map<string, Map<string, NotifiedReaction>>();

function reaction_identity_key(user_id: number, emoji_detail: ReactionEmojiDetail): string {
    // A reaction is uniquely identified by who reacted and with which
    // emoji; reaction_type namespaces emoji_code (e.g. a Unicode
    // codepoint versus a realm emoji id).
    return `${user_id}:${emoji_detail.reaction_type}:${emoji_detail.emoji_code}`;
}

function render_reaction_emoji(emoji_detail: ReactionEmojiDetail): string {
    // Realm emoji (including the special :zulip: emoji) and the text
    // emojiset are rendered as `:emoji_name:`; unicode emoji are rendered
    // as the glyph itself. We render from the reaction event's own fields
    // rather than looking the name up in `emoji.emojis_by_name`, since
    // that map excludes deactivated realm emoji, which can still receive
    // reactions (and thus generate notifications).
    const is_realm_emoji = emoji_detail.reaction_type !== "unicode_emoji";
    if (is_realm_emoji || user_settings.emojiset === "text") {
        return `:${emoji_detail.emoji_name}:`;
    }
    return ui_util.convert_emoji_code_to_unicode(emoji_detail.emoji_code) ?? ":invalid_emoji:";
}

function get_reaction_notification_title(reactions: Map<string, NotifiedReaction>): string {
    // Derive the distinct reactors and emoji from the individual
    // reactions, re-inserting each so that its most recent occurrence
    // determines the order (newest last).
    const emojis = new Map<string, ReactionEmojiDetail>();
    const user_ids = new Set<number>();
    for (const {user_id, emoji_detail} of reactions.values()) {
        emojis.delete(emoji_detail.emoji_name);
        emojis.set(emoji_detail.emoji_name, emoji_detail);
        user_ids.delete(user_id);
        user_ids.add(user_id);
    }

    const user_ids_list = [...user_ids];
    assert(user_ids_list.length > 0);
    const username = people.get_display_full_name(user_ids_list.at(-1)!);
    const rendered_emojis: string[] = [];
    for (const emoji_detail of [...emojis.values()].toReversed()) {
        rendered_emojis.push(render_reaction_emoji(emoji_detail));
    }
    const rendered_emoji = rendered_emojis.join(", ");

    if (user_ids_list.length === 1) {
        return $t(
            {defaultMessage: "{username} reacted with {rendered_emoji}"},
            {username, rendered_emoji},
        );
    }

    if (user_ids_list.length === 2) {
        const other_username = people.get_display_full_name(user_ids_list[0]!);
        return $t(
            {
                defaultMessage: "{username} and {other_username} reacted with {rendered_emoji}",
            },
            {username, other_username, rendered_emoji},
        );
    }

    const other_reactions_count = user_ids_list.length - 1;

    return $t(
        {
            defaultMessage:
                "{username} and {other_reactions_count} others reacted with {rendered_emoji}",
        },
        {username, other_reactions_count, rendered_emoji},
    );
}

export function reaction_is_notifiable(message: Message, user_id: number): boolean {
    // Reaction event is by the current user
    if (user_id === current_user.user_id) {
        return false;
    }

    // If the message is not sent by the current user, no need for notification.
    if (!message.sent_by_me) {
        return false;
    }

    // Do not notify if the user is muted.
    if (muted_users.is_user_muted(user_id)) {
        return false;
    }

    // Do not notify if stream is muted & topic also inherits the visibility.
    if (
        message.type === "stream" &&
        stream_data.is_muted(message.stream_id) &&
        !user_topics.is_topic_unmuted_or_followed(message.stream_id, message.topic)
    ) {
        return false;
    }

    // Do not notify if topic is muted.
    if (message.type === "stream" && user_topics.is_topic_muted(message.stream_id, message.topic)) {
        return false;
    }

    return true;
}

export function process_notification(notification: {
    message: Message;
    reaction_event: ReactionEvent;
    desktop_notify: boolean;
}): void {
    if (!notification.desktop_notify || desktop_notifications.NotificationAPI === undefined) {
        return;
    }

    const reaction_event = notification.reaction_event;
    const message = notification.message;
    const key = message.id.toString();
    const emoji_detail: ReactionEmojiDetail = {
        emoji_name: reaction_event.emoji_name,
        emoji_code: reaction_event.emoji_code,
        reaction_type: reaction_event.reaction_type,
    };

    const reactions = message_reactions.get(key) ?? new Map<string, NotifiedReaction>();

    // Record this reaction, moving it to the end so the newest reactions
    // and reactors render first in the notification title.
    const reaction_key = reaction_identity_key(reaction_event.user_id, emoji_detail);
    reactions.delete(reaction_key);
    reactions.set(reaction_key, {user_id: reaction_event.user_id, emoji_detail});
    message_reactions.set(key, reactions);

    // The title credits the newest reactor first (see
    // get_reaction_notification_title), so we show their avatar.
    const icon_url = people.small_avatar_url_for_person(
        people.get_by_user_id(reaction_event.user_id),
    );
    const opts = {
        icon: icon_url,
        body: message_notification.get_notification_content(message),
        tag: key,
    };
    const title = get_reaction_notification_title(reactions);

    function on_click(): void {
        // Narrow using the captured message rather than looking it up by
        // id, so a click still works if the message was deleted before
        // narrowing, matching message_notifications' behavior.
        message_view.narrow_to_message_near(message, "notification");
    }

    function on_close(): void {
        message_reactions.delete(key);
    }

    const msg_count = 1;
    desktop_notifications.create_notification(
        opts,
        key,
        title,
        message.id,
        msg_count,
        on_click,
        on_close,
    );
}

function reaction_audible_notifications_enabled(): boolean {
    return (
        user_settings.notification_sound !== "none" &&
        user_settings.enable_reaction_audible_notifications
    );
}

function reaction_notifications_enabled(): boolean {
    // Desktop notifications only fire when the browser permission has been
    // granted, so we require it here. Otherwise received_reaction would
    // fetch uncached messages that could never produce a notification (nor
    // a sound, when audible notifications are also off).
    const desktop_notifications_will_fire =
        user_settings.enable_reaction_desktop_notifications &&
        desktop_notifications.granted_desktop_notifications_permission();
    return desktop_notifications_will_fire || reaction_audible_notifications_enabled();
}

function process_reaction_event(message: Message, event: ReactionEvent): void {
    if (!reaction_is_notifiable(message, event.user_id)) {
        return;
    }

    if (user_settings.enable_reaction_desktop_notifications) {
        process_notification({
            message,
            reaction_event: event,
            desktop_notify: desktop_notifications.granted_desktop_notifications_permission(),
        });
    }

    if (reaction_audible_notifications_enabled()) {
        void ui_util.play_audio(util.the($("#user-notification-sound-audio")));
    }
}

export function received_reaction(event: ReactionEvent): void {
    // Reaction events are delivered to everyone who can see the message,
    // so we run the checks that don't depend on the message here, before
    // potentially fetching an uncached message from the server below.
    // Otherwise we would make a server request for essentially every
    // reaction in a busy channel, the vast majority of which can never
    // notify this user.

    // A reaction by the current user never notifies.
    if (event.user_id === current_user.user_id) {
        return;
    }

    // If the user is actively looking at Zulip, the reaction is visible
    // live in the message feed, so a notification would just be noise.
    if (unread_ops.is_window_focused()) {
        return;
    }

    if (!reaction_notifications_enabled()) {
        return;
    }

    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message !== undefined) {
        process_reaction_event(message, event);
    } else {
        // We do not have message in the message cache, we should ask for the
        // message from server and show notification.
        void channel.get({
            url: "/json/messages/" + message_id,
            data: {allow_empty_topic_name: true},
            success(raw_data) {
                const data = fetch_message_response_schema.parse(raw_data);
                const message = message_helper.process_new_server_message(data.message);
                process_reaction_event(message, event);
            },
            error() {
                blueslip.info("Failed to fetch message for reaction notification");
            },
        });
    }
}

export function remove_reaction_notification(event: ReactionEvent): void {
    // Called when a reaction is removed. We drop just that reaction from
    // our tracked state, rather than dismissing the whole notification,
    // so that reactions from other users (or other emoji) are preserved.
    const key = event.message_id.toString();
    const reactions = message_reactions.get(key);
    if (reactions === undefined) {
        return;
    }

    const reaction_key = reaction_identity_key(event.user_id, {
        emoji_name: event.emoji_name,
        emoji_code: event.emoji_code,
        reaction_type: event.reaction_type,
    });
    if (!reactions.delete(reaction_key)) {
        // This reaction was never part of the notification, so there is
        // nothing to update.
        return;
    }

    if (reactions.size === 0) {
        // No notified reactions remain, so dismiss the notification.
        // close_notification runs the notification's on_close, which
        // clears our message_reactions entry.
        desktop_notifications.close_notification(event.message_id);
    }
}
