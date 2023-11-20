import $ from "jquery";

import * as desktop_notifications from "./desktop_notifications";
// eslint-disable-next-line import/no-cycle
import * as message_notifications from "./message_notifications";
import * as ui_util from "./ui_util";
import {user_settings} from "./user_settings";
import * as user_topics from "./user_topics";

export function reaction_is_notifiable(message) {
    if (message.current_user_reacted) {
        return false;
    }

    if (!message.sent_by_me) {
        return false;
    }

    if (message.type === "private" && user_settings.enable_dm_reactions_notifications) {
        return true;
    }

    if (
        message.type === "stream" &&
        user_topics.is_topic_followed(message.stream_id, message.topic) &&
        user_settings.enable_followed_topics_reactions_notifications
    ) {
        return true;
    }

    if (
        message.type === "stream" &&
        !user_topics.is_topic_unmuted(message.stream_id, message.topic) &&
        user_settings.enable_unmuted_topic_reactions_notifications
    ) {
        return true;
    }

    // Everything else is on the table; next filter based on notification
    // settings.
    return false;
}

export function received_reaction(message) {
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
        ui_util.play_audio($("#user-notification-sound-audio")[0]);
    }
}
