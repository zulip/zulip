import $ from "jquery";

import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as message_store from "./message_store";
import * as narrow from "./narrow";
import * as stream_data from "./stream_data";

if (window.electron_bridge !== undefined) {
    window.electron_bridge.on_event("logout", () => {
        $("#logout_form").trigger("submit");
    });

    window.electron_bridge.on_event("show-keyboard-shortcuts", () => {
        browser_history.go_to_location("keyboard-shortcuts");
    });

    window.electron_bridge.on_event("show-notification-settings", () => {
        browser_history.go_to_location("settings/notifications");
    });

    // The code below is for sending a message received from notification reply which
    // is often referred to as inline reply feature. This is done so desktop app doesn't
    // have to depend on channel.post for setting crsf_token and narrow.by_topic
    // to narrow to the message being sent.
    if (window.electron_bridge.set_send_notification_reply_message_supported !== undefined) {
        window.electron_bridge.set_send_notification_reply_message_supported(true);
    }
    window.electron_bridge.on_event("send_notification_reply_message", (message_id, reply) => {
        const message = message_store.get(message_id);
        const data = {
            type: message.type,
            content: reply,
            topic: message.topic,
        };
        if (message.type === "private") {
            data.to = message.reply_to;
        } else {
            data.to = stream_data.get_stream_name_from_id(message.stream_id);
        }

        function success() {
            if (message.type === "stream") {
                narrow.by_topic(message_id, {trigger: "desktop_notification_reply"});
            } else {
                narrow.by_recipient(message_id, {trigger: "desktop_notification_reply"});
            }
        }

        function error(error) {
            window.electron_bridge.send_event("send_notification_reply_message_failed", {
                data,
                message_id,
                error,
            });
        }

        channel.post({
            url: "/json/messages",
            data,
            success,
            error,
        });
    });
}
