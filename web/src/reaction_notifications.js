import $ from "jquery";

import * as desktop_notifications from "./desktop_notifications";
import {$t} from "./i18n";
import * as message_notifications from "./message_notifications";
import * as message_store from "./message_store";
import * as people from "./people";
import {get_local_reaction_id} from "./reactions";
import * as settings_config from "./settings_config";
import {current_user} from "./state_data";
import * as ui_util from "./ui_util";
import {user_settings} from "./user_settings";
import * as user_topics from "./user_topics";

function generate_notification_title(emoji_name, user_ids) {
    const usernames = people.get_display_full_names(
        user_ids.filter((user_id) => user_id !== current_user.user_id),
    );

    const current_user_reacted = user_ids.length !== usernames.length;

    const context = {
        emoji_name: ":" + emoji_name + ":",
    };

    if (user_ids.length === 1) {
        context.username = usernames[0];
        return $t({defaultMessage: "{username} reacted with {emoji_name}."}, context);
    }

    if (user_ids.length === 2 && current_user_reacted) {
        context.other_username = usernames[0];
        return $t(
            {
                defaultMessage: "You and {other_username} reacted with {emoji_name}.",
            },
            context,
        );
    }

    context.total_reactions = usernames.length;
    context.last_username = usernames.at(-1);

    return $t(
        {
            defaultMessage:
                "{last_username} and {total_reactions} others reacted with {emoji_name}.",
        },
        context,
    );
}

export function reaction_is_notifiable(message) {
    // If the current user reacted, no need for notification.
    if (message.current_user_reacted) {
        return false;
    }

    // If the message is not sent by the current user, no need for notification.
    if (!message.sent_by_me) {
        return false;
    }

    // Notify for reactions in private messages if the user has enabled DM reaction notifications.
    if (message.type === "private" && user_settings.enable_dm_reaction_notifications) {
        return true;
    }

    // Notify for reactions in stream messages if the user has set stream reaction notifications to "Always".
    if (
        message.type === "stream" &&
        user_settings.streams_reaction_notification ===
            settings_config.streams_reaction_notification_values.always.code
    ) {
        return true;
    }

    // Do not notify for reactions in stream messages if the user has set stream reaction notifications to "Never".
    if (
        message.type === "stream" &&
        user_settings.streams_reaction_notification ===
            settings_config.streams_reaction_notification_values.never.code
    ) {
        return false;
    }

    // Notify for reactions in stream messages if the message's topic is followed by the user
    // and the user has set stream reaction notifications to "Followed topics".
    if (
        message.type === "stream" &&
        user_topics.is_topic_followed(message.stream_id, message.topic) &&
        user_settings.streams_reaction_notification ===
            settings_config.streams_reaction_notification_values.followed_topics.code
    ) {
        return true;
    }

    // Notify for reactions in stream messages if the message's topic is unmuted by the user
    // and the user has set stream reaction notifications to "Unmuted topics".
    if (
        message.type === "stream" &&
        user_topics.is_topic_unmuted(message.stream_id, message.topic) &&
        user_settings.streams_reaction_notification ===
            settings_config.streams_reaction_notification_values.unmuted_topics.code
    ) {
        return true;
    }

    // Everything else is on the table; next filter based on notification
    // settings.
    return false;
}

export function received_reaction(event) {
    const message_id = event.message_id;
    const message = message_store.get(message_id);

    if (message === undefined) {
        // If we don't have the message in cache, do nothing; if we
        // ever fetch it from the server, it'll come with the
        // latest reactions attached
        return;
    }

    const user_id = event.user_id;
    const local_id = get_local_reaction_id(event);
    const clean_reaction_object = message.clean_reactions.get(local_id);

    message.current_user_reacted = user_id === current_user.user_id;
    message.current_reaction_key = clean_reaction_object.emoji_name;
    message.reaction_label = generate_notification_title(
        clean_reaction_object.emoji_name,
        clean_reaction_object.user_ids,
    );
    message.reacted_by = people.get_full_name(user_id);

    if (!reaction_is_notifiable(message)) {
        return;
    }

    if (message_notifications.should_send_desktop_notification(message)) {
        message_notifications.process_notification({
            message,
            desktop_notify: desktop_notifications.granted_desktop_notifications_permission(),
        });
    }
    if (message_notifications.should_send_audible_notification(message)) {
        ui_util.play_audio($("#user-notification-sound-audio").get(0));
    }
}
