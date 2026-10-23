import {$} from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import type {NotifiedReaction} from "./desktop_notifications.ts";
import type {EmojiRenderingDetails} from "./emoji.ts";
import {$t} from "./i18n.ts";
import * as message_notifications from "./message_notifications.ts";
import type {Message} from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as message_viewport from "./message_viewport.ts";
import * as people from "./people.ts";
import * as reactions from "./reactions.ts";
import type {ReactionEvent} from "./reactions.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

function notified_reactions_for_message(
    message_id: number,
): Map<string, NotifiedReaction> | undefined {
    // The reactions credited in this message's live reaction
    // notification, keyed by reaction event key and ordered by
    // arrival.
    const notice_mem_entry = desktop_notifications.notice_memory.get(message_id.toString());
    if (notice_mem_entry?.data.type !== "reaction") {
        return undefined;
    }
    return notice_mem_entry.data.reactions;
}

function render_reaction_emoji(emoji_detail: EmojiRenderingDetails): string {
    // Realm emoji and the text emojiset render as `:emoji_name:`, unicode
    // emoji as the glyph. We use the event's own fields, since
    // `emoji.emojis_by_name` leaves out deactivated realm emoji, which can
    // still receive reactions.
    const is_realm_emoji = emoji_detail.reaction_type !== "unicode_emoji";
    if (is_realm_emoji || user_settings.emojiset === "text") {
        return `:${emoji_detail.emoji_name}:`;
    }

    const emoji_unicode = util.convert_emoji_code_to_unicode(emoji_detail.emoji_code);
    if (emoji_unicode === undefined) {
        blueslip.error("Invalid unicode codepoint for emoji", {
            emoji_code: emoji_detail.emoji_code,
            emoji_name: emoji_detail.emoji_name,
        });
        return `:${emoji_detail.emoji_name}:`;
    }
    return emoji_unicode;
}

function get_reaction_notification_title(
    notified_reactions: Map<string, NotifiedReaction>,
): string {
    // The distinct reactors and emoji, each ordered by its most recent
    // reaction, newest last. Emoji are de-duplicated by how they render:
    // a realm emoji that replaced a deactivated one of the same name
    // renders the same, while one named after a unicode emoji does not.
    const rendered_emojis = new Set<string>();
    const user_ids = new Set<number>();
    for (const {user_id, emoji_detail} of notified_reactions.values()) {
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
                "{username} and {other_users_count, plural, one {# other} other {# others}} reacted with {rendered_emoji}",
        },
        {username, other_users_count, rendered_emoji},
    );
}

export function reaction_is_notifiable(message: Message): boolean {
    if (!user_topics.is_message_visible_in_home(message)) {
        return false;
    }

    // Not a reaction the user is watching arrive.
    return !message_viewport.is_message_on_screen(message);
}

export function process_notification(notification: {
    message: Message;
    reaction_events: ReactionEvent[];
}): void {
    // One notification for all of these reactions to the message, which
    // arrive in order, newest last.
    const reaction_events = notification.reaction_events;
    const message = notification.message;
    const key = message.id.toString();

    const notified_reactions =
        notified_reactions_for_message(message.id) ?? new Map<string, NotifiedReaction>();

    // Record these reactions in the notification.
    for (const reaction_event of reaction_events) {
        const emoji_detail: EmojiRenderingDetails = {
            emoji_name: reaction_event.emoji_name,
            emoji_code: reaction_event.emoji_code,
            reaction_type: reaction_event.reaction_type,
        };
        const reaction_key = reactions.get_reaction_event_key(reaction_event);
        notified_reactions.set(reaction_key, {user_id: reaction_event.user_id, emoji_detail});
    }

    // The title credits the newest reactor first (see
    // get_reaction_notification_title), so we show their avatar.
    const newest_reaction_event = reaction_events.at(-1);
    assert(newest_reaction_event !== undefined);
    const reactor = people.get_user_by_id_assert_valid(newest_reaction_event.user_id);
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
    const title = get_reaction_notification_title(notified_reactions);

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
        data: {type: "reaction", message_id: message.id, reactions: notified_reactions},
        on_click,
    });
}

function reaction_audible_notifications_enabled(): boolean {
    return (
        user_settings.notification_sound !== "none" &&
        user_settings.enable_reaction_audible_notifications
    );
}

export function reaction_notifications_enabled(): boolean {
    // A desktop notification needs the browser's permission. Without it,
    // and with sounds off, nothing can result.
    const desktop_notifications_will_fire =
        user_settings.enable_reaction_desktop_notifications &&
        desktop_notifications.granted_desktop_notifications_permission();
    return desktop_notifications_will_fire || reaction_audible_notifications_enabled();
}

export function send_reaction_notifications(
    message: Message,
    reaction_events: ReactionEvent[],
): void {
    // Notifies once about new reactions to a message, however many
    // arrived together.
    if (!reaction_is_notifiable(message)) {
        return;
    }

    if (user_settings.enable_reaction_desktop_notifications) {
        process_notification({message, reaction_events});
    }

    if (reaction_audible_notifications_enabled()) {
        void ui_util.play_audio(util.the($("#user-notification-sound-audio")));
    }
}

export function remove_reaction_notification(event: ReactionEvent): void {
    // Drops just this reaction, so that the notification keeps crediting
    // the others.
    const reaction_key = reactions.get_reaction_event_key(event);
    const notified_reactions = notified_reactions_for_message(event.message_id);
    if (notified_reactions === undefined) {
        return;
    }

    if (!notified_reactions.delete(reaction_key)) {
        // Never part of the notification.
        return;
    }

    // With reactions left, the notification keeps its title, which still
    // credits this one: replacing it would re-pop it for something the
    // user no longer needs to see. The next reaction to the message builds
    // its title from the pruned reactions.
    if (notified_reactions.size === 0) {
        // Closing the notification also discards its stored reactions.
        desktop_notifications.close_notification(event.message_id);
    }
}
