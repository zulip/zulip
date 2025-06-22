import {$} from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import {$t} from "./i18n.ts";
import * as message_helper from "./message_helper.ts";
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

const fetch_messages_response_schema = z.object({
    messages: z.array(raw_message_schema),
});

type ReactionEmojiDetail = Pick<ReactionEvent, "emoji_name" | "emoji_code" | "reaction_type">;

export type ReactionNotificationEvent = ReactionEvent & {op: "add" | "remove"};

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

// Reactions we are fetching an uncached message for, keyed by message id
// and then reaction_identity_key. A reaction that is retracted while its
// fetch is in flight is dropped from here, so that the fetch does not go
// on to notify about a reaction that no longer exists.
const pending_reaction_fetches = new Map<string, Set<string>>();

function reaction_identity_key(user_id: number, emoji_detail: ReactionEmojiDetail): string {
    // A reaction is uniquely identified by who reacted and with which
    // emoji; reaction_type namespaces emoji_code (e.g. a Unicode
    // codepoint versus a realm emoji id).
    return `${user_id}:${emoji_detail.reaction_type}:${emoji_detail.emoji_code}`;
}

function reaction_event_identity_key(event: ReactionEvent): string {
    return reaction_identity_key(event.user_id, {
        emoji_name: event.emoji_name,
        emoji_code: event.emoji_code,
        reaction_type: event.reaction_type,
    });
}

function add_pending_reaction_fetch(key: string, reaction_key: string): void {
    const pending = pending_reaction_fetches.get(key);
    if (pending === undefined) {
        pending_reaction_fetches.set(key, new Set([reaction_key]));
        return;
    }
    pending.add(reaction_key);
}

function discard_pending_reaction_fetch(key: string, reaction_key: string): boolean {
    // Returns whether this reaction was still awaiting its fetch, so
    // callers can tell a reaction that is still live from one that was
    // retracted while we were fetching its message.
    const pending = pending_reaction_fetches.get(key);
    if (pending === undefined) {
        return false;
    }
    const was_pending = pending.delete(reaction_key);
    if (pending.size === 0) {
        pending_reaction_fetches.delete(key);
    }
    return was_pending;
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

    const emoji_unicode = ui_util.convert_emoji_code_to_unicode(emoji_detail.emoji_code);
    if (emoji_unicode === undefined) {
        blueslip.error("Invalid unicode codepoint for emoji", {
            emoji_code: emoji_detail.emoji_code,
            emoji_name: emoji_detail.emoji_name,
        });
        return `:${emoji_detail.emoji_name}:`;
    }
    return emoji_unicode;
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
    const rendered_emojis = emojis
        .values()
        .toArray()
        .toReversed()
        .map((emoji_detail) => render_reaction_emoji(emoji_detail));
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

    const other_users_count = user_ids_list.length - 1;

    return $t(
        {
            defaultMessage:
                "{username} and {other_users_count} others reacted with {rendered_emoji}",
        },
        {username, other_users_count, rendered_emoji},
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
    const icon_url = people.small_avatar_url_for_user_id(reaction_event.user_id);
    const notification_options = {
        icon: icon_url,
        body: desktop_notifications.get_notification_content(message, "reaction"),
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
    desktop_notifications.create_notification({
        notification_options,
        key,
        title,
        message_id: message.id,
        msg_count,
        on_click,
        on_close,
    });
}

function reaction_audible_notifications_enabled(): boolean {
    return (
        user_settings.notification_sound !== "none" &&
        user_settings.enable_reaction_audible_notifications
    );
}

function reaction_notifications_enabled(): boolean {
    // Desktop notifications only fire when the browser permission has been
    // granted, so we require it here. Otherwise received_reactions would
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

function discard_pending_reaction_fetches(
    reactions_by_message_id: Map<number, ReactionEvent[]>,
): void {
    for (const [message_id, reaction_events] of reactions_by_message_id) {
        for (const event of reaction_events) {
            discard_pending_reaction_fetch(
                message_id.toString(),
                reaction_event_identity_key(event),
            );
        }
    }
}

function fetch_messages_for_reactions(reactions_by_message_id: Map<number, ReactionEvent[]>): void {
    // A batch of events can carry reactions to several messages we do
    // not have cached, which is typical when a user returns to an idle
    // Zulip. We fetch all of those messages in a single request, rather
    // than one per reaction.
    void channel.get({
        url: "/json/messages",
        data: {
            message_ids: JSON.stringify(reactions_by_message_id.keys().toArray()),
            allow_empty_topic_name: true,
        },
        success(raw_data) {
            const data = fetch_messages_response_schema.parse(raw_data);
            // Cache the messages regardless of whether we still want to
            // notify, so later reactions to them skip this fetch.
            const fetched_messages = new Map(
                data.messages.map((raw_message) => [
                    raw_message.id,
                    message_helper.process_new_server_message(raw_message),
                ]),
            );

            for (const [message_id, reaction_events] of reactions_by_message_id) {
                // A message the current user can no longer access --
                // deleted, or moved somewhere they cannot see it -- is
                // simply absent from the response.
                const message = fetched_messages.get(message_id);
                for (const event of reaction_events) {
                    const was_pending = discard_pending_reaction_fetch(
                        message_id.toString(),
                        reaction_event_identity_key(event),
                    );
                    if (!was_pending) {
                        // The reacting user retracted this reaction while
                        // we were fetching its message. A removal is not
                        // new activity, so there is nothing to notify
                        // about.
                        continue;
                    }
                    if (message !== undefined) {
                        process_reaction_event(message, event);
                    }
                }
            }
        },
        error() {
            discard_pending_reaction_fetches(reactions_by_message_id);
            blueslip.info("Failed to fetch messages for reaction notifications");
        },
    });
}

function reaction_event_may_notify(event: ReactionEvent): boolean {
    // A reaction by the current user never notifies.
    if (event.user_id === current_user.user_id) {
        return false;
    }

    // Only reactions to the current user's own messages notify. The event
    // carries the message's sender, so reactions to everyone else's
    // messages -- nearly all of them in an active organization -- are
    // dropped without a request for a message we cannot use.
    return event.message_sender_id === current_user.user_id;
}

export function received_reactions(events: ReactionNotificationEvent[]): void {
    // Reaction events are delivered to everyone who can see the message,
    // so we run the checks that don't depend on the message here, before
    // potentially fetching uncached messages from the server below.
    // Otherwise we would make server requests for essentially every
    // reaction in a busy channel, the vast majority of which can never
    // notify this user.
    //
    // If Zulip is focused, the reactions are visible live in the message
    // feed, so notifications would just be noise.
    const can_notify = !unread_ops.is_window_focused() && reaction_notifications_enabled();

    // The reactions whose message we need to fetch, keyed by message id
    // and in arrival order, so that the whole batch shares one request.
    const reactions_by_message_id = new Map<number, ReactionEvent[]>();

    for (const event of events) {
        if (event.op === "remove") {
            // Removals are processed even when we would not notify, since
            // they dismiss notifications shown for earlier reactions.
            remove_reaction_notification(event);
            continue;
        }

        if (!can_notify || !reaction_event_may_notify(event)) {
            continue;
        }

        const message = message_store.get(event.message_id);
        if (message !== undefined) {
            process_reaction_event(message, event);
            continue;
        }

        add_pending_reaction_fetch(event.message_id.toString(), reaction_event_identity_key(event));
        const reactions = reactions_by_message_id.get(event.message_id) ?? [];
        reactions.push(event);
        reactions_by_message_id.set(event.message_id, reactions);
    }

    // A reaction retracted by a later event in the same batch was
    // discarded from the pending set above, which can leave a message
    // with nothing left to notify about; fetching it would be pointless.
    // (An empty pending set is deleted, so a missing key means none of
    // this batch's reactions to that message survived.)
    for (const message_id of reactions_by_message_id.keys()) {
        if (!pending_reaction_fetches.has(message_id.toString())) {
            reactions_by_message_id.delete(message_id);
        }
    }

    if (reactions_by_message_id.size > 0) {
        fetch_messages_for_reactions(reactions_by_message_id);
    }
}

function remove_reaction_notification(event: ReactionEvent): void {
    // Called when a reaction is removed. We drop just that reaction from
    // our tracked state, rather than dismissing the whole notification,
    // so that reactions from other users (or other emoji) are preserved.
    const key = event.message_id.toString();
    const reaction_key = reaction_event_identity_key(event);

    // If we are still fetching this reaction's message, cancel that
    // pending notification; otherwise the fetch would pop a notification
    // for a reaction that has already been retracted, and nothing would
    // dismiss it, since no reaction remains to be removed later.
    discard_pending_reaction_fetch(key, reaction_key);

    const reactions = message_reactions.get(key);
    if (reactions === undefined) {
        return;
    }

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
