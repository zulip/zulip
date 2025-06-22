import $ from "jquery";
import {z} from "zod";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import type {ElectronBridgeNotification} from "./desktop_notifications.ts";
import * as emoji from "./emoji.ts";
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
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

const fetch_message_response_schema = z.object({
    message: raw_message_schema,
});

function convert_emoji_code_to_unicode(emoji_code: string): string {
    const emoji_code_parts = emoji_code.split("-");
    const emoji_unicode_parts: string[] = [];

    for (const part of emoji_code_parts) {
        const emoji_code_int = Number.parseInt(part, 16);
        if (Number.isNaN(emoji_code_int) || !(emoji_code_int >= 0 && emoji_code_int <= 0x10ffff)) {
            return ":invalid_emoji:";
        }
        emoji_unicode_parts.push(String.fromCodePoint(emoji_code_int));
    }

    return emoji_unicode_parts.join("");
}

function get_reaction_notification_title(emoji_set: Set<string>, user_ids: Set<number>): string {
    const user_ids_list = [...user_ids];

    const username = people.get_display_full_name(user_ids_list.at(-1)!);
    const rendered_emojis: string[] = [];
    for (const emoji_name of [...emoji_set].reverse()) {
        const emoji_detail = emoji.emojis_by_name.get(emoji_name)!;
        const emoji_alt_code = user_settings.emojiset === "text";

        const rendered =
            emoji_detail.is_realm_emoji || emoji_alt_code
                ? `:${emoji_detail.name}:`
                : convert_emoji_code_to_unicode(emoji_detail.emoji_code);

        rendered_emojis.push(rendered);
    }
    const rendered_emoji = rendered_emojis.join(",");

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

    const total_reactions = user_ids_list.length - 1;

    return $t(
        {
            defaultMessage: "{username} and {total_reactions} others reacted with {rendered_emoji}",
        },
        {username, total_reactions, rendered_emoji},
    );
}

export function reaction_is_notifiable(message: Message): boolean {
    // If the message is not sent by the current user, no need for notification.
    if (!message.sent_by_me) {
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
    const reaction_event = notification.reaction_event;
    const message = notification.message;
    const user_id = reaction_event.user_id;
    const key = message.id.toString();
    const emoji_name = reaction_event.emoji_name;
    const content = message_notification.get_notification_content(message);
    let notification_object: ElectronBridgeNotification | Notification;
    const msg_count = 1;
    let emoji_set = new Set([emoji_name]);
    let user_ids = new Set([user_id]);

    const notice_memory = desktop_notifications.notice_memory.get(key);
    if (notice_memory) {
        if (notice_memory.reaction_list!.emoji_set.has(emoji_name)) {
            notice_memory.reaction_list!.emoji_set.delete(emoji_name);
        }
        notice_memory.reaction_list!.emoji_set.add(emoji_name);
        emoji_set = new Set(notice_memory.reaction_list!.emoji_set);
        notice_memory.reaction_list!.user_ids.add(user_id);
        user_ids = new Set(notice_memory.reaction_list!.user_ids);
        notification_object = notice_memory.obj;
        notification_object.close();
    }

    const title = get_reaction_notification_title(emoji_set, user_ids);

    if (notification.desktop_notify && desktop_notifications.NotificationAPI !== undefined) {
        const user = people.get_by_user_id(reaction_event.user_id);
        const icon_url = people.small_avatar_url_for_person(user);
        notification_object = new desktop_notifications.NotificationAPI(title, {
            icon: icon_url,
            body: content,
            tag: message.id.toString(),
        });
        const reaction_list = {emoji_set, user_ids};
        desktop_notifications.notice_memory.set(key, {
            obj: notification_object,
            msg_count,
            message_id: message.id,
            reaction_list,
        });

        if (typeof notification_object.addEventListener === "function") {
            // Sadly, some third-party Electron apps like Franz/Ferdi
            // misimplement the Notification API not inheriting from
            // EventTarget.  This results in addEventListener being
            // unavailable for them.
            notification_object.addEventListener("click", () => {
                notification_object.close();
                message_view.narrow_by_topic(message.id, {trigger: "notification"});
                window.focus();
            });
            notification_object.addEventListener("close", () => {
                desktop_notifications.notice_memory.delete(key);
            });
        }
    }
}

function process_reaction_event(message: Message, event: ReactionEvent): void {
    const user_id = event.user_id;
    if (user_id === current_user.user_id) {
        return;
    }

    if (!reaction_is_notifiable(message)) {
        return;
    }

    if (user_settings.enable_reaction_desktop_notifications) {
        process_notification({
            message,
            reaction_event: event,
            desktop_notify: desktop_notifications.granted_desktop_notifications_permission(),
        });
    }

    if (
        user_settings.notification_sound !== "none" &&
        user_settings.enable_reaction_audible_notifications
    ) {
        void ui_util.play_audio(util.the($("#user-notification-sound-audio")));
    }
}

export function received_reaction(event: ReactionEvent): void {
    // Do not notify if the user is muted.
    if (muted_users.is_user_muted(event.user_id)) {
        return;
    }

    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message !== undefined) {
        process_reaction_event(message, event);
    }

    // We do not have message in the message cache, we should ask for the
    // message from server and show notification.
    if (message === undefined) {
        void channel.get({
            url: "/json/messages/" + message_id,
            data: {allow_empty_topic_name: true},
            success(raw_data) {
                const data = fetch_message_response_schema.parse(raw_data);
                const message = message_helper.process_new_message(data.message);
                process_reaction_event(message, event);
            },
            error() {
                blueslip.info("Failed to fetch message for reaction notification");
            },
        });
    }
}
