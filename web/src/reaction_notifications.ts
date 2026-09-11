import {$} from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import type {NotifiedReaction} from "./desktop_notifications.ts";
import type {EmojiRenderingDetails} from "./emoji";
import {$t} from "./i18n.ts";
import * as message_helper from "./message_helper.ts";
import * as message_lists from "./message_lists.ts";
import * as message_notifications from "./message_notifications.ts";
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

export type ReactionNotificationEvent = ReactionEvent & {op: "add" | "remove"};

// The reactions we still intend to notify about, as one set of
// pending_reaction_key values per batch of events -- held while the batch
// is being processed, and then for as long as a request it started is
// fetching messages. A reaction that is retracted before we act on it is
// dropped from whichever sets are holding it, so that we do not go on to
// notify about a reaction that no longer exists. Each batch owns its own
// set, so that one can neither cancel nor revive another's pending
// notifications when the same reaction is added, retracted, and added
// again while a fetch is outstanding.
const pending_reaction_notification_sets = new Set<Set<string>>();

function notified_reactions_for_message(
    message_id: number,
): Map<string, NotifiedReaction> | undefined {
    // The reactions credited in this message's live reaction
    // notification, keyed by reaction_identity_key and ordered by
    // arrival.
    const notice_mem_entry = desktop_notifications.notice_memory.get(message_id.toString());
    if (notice_mem_entry?.data.type !== "reaction") {
        return undefined;
    }
    return notice_mem_entry.data.reactions;
}

function reaction_identity_key(user_id: number, emoji_detail: EmojiRenderingDetails): string {
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

function pending_reaction_key(event: ReactionEvent): string {
    // Identifies one reaction across messages, so that a single set can
    // track every reaction an in-flight request will notify about.
    return `${event.message_id}:${reaction_event_identity_key(event)}`;
}

function discard_pending_reaction(event: ReactionEvent): void {
    // Cancels the pending notification for a retracted reaction, in the
    // batch still being processed and in any request already fetching its
    // message.
    const key = pending_reaction_key(event);
    for (const pending_keys of pending_reaction_notification_sets) {
        pending_keys.delete(key);
    }
}

function render_reaction_emoji(emoji_detail: EmojiRenderingDetails): string {
    // Realm emoji and the text emojiset are rendered as `:emoji_name:`;
    // unicode emoji are rendered as the glyph itself. We render from the
    // reaction event's own fields rather than looking the name up in
    // `emoji.emojis_by_name`, since that map excludes deactivated realm
    // emoji, which can still receive reactions (and thus generate notifications).
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
    // determines the order (newest last). The emoji are de-duplicated by
    // how they render, not by name or by reaction identity: two distinct
    // reactions can render identically (a realm emoji that replaced a
    // deactivated one of the same name), and two reactions that share a
    // name can render differently (a realm emoji may be named after a
    // Unicode emoji, so both can be reacted with on one message).
    const rendered_emojis = new Set<string>();
    const user_ids = new Set<number>();
    for (const {user_id, emoji_detail} of reactions.values()) {
        const rendering = render_reaction_emoji(emoji_detail);
        rendered_emojis.delete(rendering);
        rendered_emojis.add(rendering);
        user_ids.delete(user_id);
        user_ids.add(user_id);
    }

    const user_ids_list = [...user_ids];
    assert(user_ids_list.length > 0);
    const username = people.get_display_full_name(user_ids_list.at(-1)!);
    const rendered_emoji = [...rendered_emojis].toReversed().join(", ");

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

function message_is_in_focused_view(message: Message): boolean {
    // Whether the user is currently looking at this message. Reactions visible
    // in the current feed don't need a notification. Being focused on another
    // conversation should still notify, as with message notifications.
    // viewport_is_visible_and_focused handles background tabs, overlays/modals,
    // and views that replace the message feed.
    return (
        unread_ops.viewport_is_visible_and_focused() &&
        message_lists.current?.get(message.id) !== undefined
    );
}

export function reaction_is_notifiable(message: Message): boolean {
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

    // Do not notify about a reaction the user is currently watching arrive.
    // Checked last so it reflects the view at notification time; the user may
    // have narrowed to or away from the message while it was being fetched.
    if (message_is_in_focused_view(message)) {
        return false;
    }

    return true;
}

export function process_notification(notification: {
    message: Message;
    reaction_event: ReactionEvent;
}): void {
    const reaction_event = notification.reaction_event;
    const message = notification.message;
    const key = message.id.toString();
    const emoji_detail: EmojiRenderingDetails = {
        emoji_name: reaction_event.emoji_name,
        emoji_code: reaction_event.emoji_code,
        reaction_type: reaction_event.reaction_type,
    };

    const reactions =
        notified_reactions_for_message(message.id) ?? new Map<string, NotifiedReaction>();

    // Record this reaction notification.
    const reaction_key = reaction_identity_key(reaction_event.user_id, emoji_detail);
    reactions.set(reaction_key, {user_id: reaction_event.user_id, emoji_detail});

    // The title credits the newest reactor first (see
    // get_reaction_notification_title), so we show their avatar.
    const reactor = people.get_user_by_id_assert_valid(reaction_event.user_id);
    const icon_url = people.small_avatar_url_for_person(reactor);
    let body;
    if (message.type === "private" && !user_settings.pm_content_in_desktop_notifications) {
        body = $t({defaultMessage: "New reaction to your direct message."});
    } else {
        body = message_notifications.get_notification_content(message);
    }
    const notification_options = {
        icon: icon_url,
        body,
        tag: key,
    };
    const title = get_reaction_notification_title(reactions);

    function on_click(): void {
        // Narrow using the captured message rather than looking it up by
        // id, so a click still works if the message was deleted before
        // narrowing, matching message_notifications' behavior.
        message_view.narrow_to_message_near(message, "notification");
    }

    desktop_notifications.create_notification({
        notification_options,
        key,
        title,
        data: {type: "reaction", message_id: message.id, reactions},
        on_click,
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
    if (!reaction_is_notifiable(message)) {
        return;
    }

    if (
        user_settings.enable_reaction_desktop_notifications &&
        desktop_notifications.granted_desktop_notifications_permission()
    ) {
        process_notification({
            message,
            reaction_event: event,
        });
    }

    if (reaction_audible_notifications_enabled()) {
        void ui_util.play_audio(util.the($("#user-notification-sound-audio")));
    }
}

function fetch_messages_for_reactions(
    reactions_by_message_id: Map<number, ReactionEvent[]>,
    pending_keys: Set<string>,
): void {
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
            pending_reaction_notification_sets.delete(pending_keys);
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
                    if (!pending_keys.delete(pending_reaction_key(event))) {
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
            pending_reaction_notification_sets.delete(pending_keys);
            blueslip.info("Failed to fetch messages for reaction notifications");
        },
    });
}

function reaction_event_may_notify(event: ReactionEvent): boolean {
    // A reaction by the current user never notifies.
    if (event.user_id === current_user.user_id) {
        return false;
    }

    // Nor does one by a user they have muted.
    if (muted_users.is_user_muted(event.user_id)) {
        return false;
    }

    // Only reactions to the current user's own messages notify.
    return event.message_sender_id === current_user.user_id;
}

export function received_reactions(events: ReactionNotificationEvent[]): void {
    // Reaction events are delivered to everyone who can see the
    // message, so filter out events that cannot notify before
    // fetching uncached messages. Whether the user is viewing the
    // message is checked later, once we have the message; uncached
    // messages cannot be in the visible feed.
    const can_notify = reaction_notifications_enabled();

    // This batch's pending notifications. We register every reaction we
    // might notify about before notifying about any of them, so that a
    // reaction retracted by a later event in the same batch is dropped
    // from the batch: reacting and unreacting while the user is away is
    // not activity worth a notification or a sound, whether or not we
    // happen to have the message cached.
    const pending_keys = new Set<string>();
    pending_reaction_notification_sets.add(pending_keys);
    let fetch_owns_pending_keys = false;

    try {
        // The reactions this batch might notify about, one entry per
        // reaction, keyed by pending_reaction_key. For add → retract →
        // add, the first add is discarded and only the latest add is kept.
        const candidate_events = new Map<string, ReactionEvent>();
        for (const event of events) {
            if (event.op === "remove") {
                // Removals are processed even when we would not notify,
                // since they dismiss notifications shown for earlier
                // reactions, and drop retracted reactions from this batch.
                remove_reaction_notification(event);
                continue;
            }

            if (!can_notify || !reaction_event_may_notify(event)) {
                continue;
            }

            const key = pending_reaction_key(event);
            pending_keys.add(key);
            candidate_events.delete(key);
            candidate_events.set(key, event);
        }

        // The whole batch has now been seen, so pending_keys holds exactly
        // the reactions that survived it. The reactions whose message we
        // need to fetch are collected by message id, in arrival order, so
        // that the whole batch shares one request.
        const reactions_by_message_id = new Map<number, ReactionEvent[]>();
        for (const [key, event] of candidate_events) {
            if (!pending_keys.has(key)) {
                // Retracted by a later event in this same batch.
                continue;
            }

            const message = message_store.get(event.message_id);
            if (message === undefined) {
                const reactions = reactions_by_message_id.get(event.message_id) ?? [];
                reactions.push(event);
                reactions_by_message_id.set(event.message_id, reactions);
                continue;
            }

            process_reaction_event(message, event);
        }

        if (reactions_by_message_id.size > 0) {
            fetch_messages_for_reactions(reactions_by_message_id, pending_keys);
            fetch_owns_pending_keys = true;
        }
    } finally {
        // Once a request is on its way, it owns these keys and unregisters
        // them when it settles. Otherwise -- including if we threw partway
        // through the batch -- nothing else will, so we do it here.
        if (!fetch_owns_pending_keys) {
            pending_reaction_notification_sets.delete(pending_keys);
        }
    }
}

function remove_reaction_notification(event: ReactionEvent): void {
    // Called when a reaction is removed. We drop just that reaction from
    // our tracked state, rather than dismissing the whole notification,
    // so that reactions from other users (or other emoji) are preserved.
    const reaction_key = reaction_event_identity_key(event);

    // If we are still fetching this reaction's message, cancel that
    // pending notification; otherwise the fetch would pop a notification
    // for a reaction that has already been retracted, and nothing would
    // dismiss it, since no reaction remains to be removed later.
    discard_pending_reaction(event);

    const reactions = notified_reactions_for_message(event.message_id);
    if (reactions === undefined) {
        return;
    }

    if (!reactions.delete(reaction_key)) {
        // This reaction was never part of the notification, so there is
        // nothing to update.
        return;
    }

    // When reactions remain, the notification stays up with the title it
    // already has, which still credits the reaction we just dropped:
    // rewriting the title means replacing the notification, which would
    // re-pop it and pull the user back to a message for something they no
    // longer need to see. The pruned reactions are what the next reaction
    // to this message builds its title from, so the staleness lasts only
    // until there is new activity worth announcing.
    if (reactions.size === 0) {
        // No notified reactions remain, so dismiss the notification;
        // closing it discards the reactions stored with it.
        desktop_notifications.close_notification(event.message_id);
    }
}
