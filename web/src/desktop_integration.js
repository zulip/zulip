import $ from "jquery";

import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import {electron_bridge} from "./electron_bridge.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {$t} from "./i18n.ts";
import * as message_store from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as stream_data from "./stream_data.ts";

export function initialize() {
    if (electron_bridge === undefined) {
        return;
    }

    electron_bridge.on_event("logout", () => {
        $("#logout_form").trigger("submit");
    });

    electron_bridge.on_event("show-keyboard-shortcuts", () => {
        browser_history.go_to_location("keyboard-shortcuts");
    });

    electron_bridge.on_event("show-notification-settings", () => {
        browser_history.go_to_location("settings/notifications");
    });

    // The code below is for sending a message received from notification reply which
    // is often referred to as inline reply feature. This is done so desktop app doesn't
    // have to depend on channel.post for setting crsf_token and message_view.narrow_by_topic
    // to narrow to the message being sent.
    electron_bridge.set_send_notification_reply_message_supported?.(true);
    electron_bridge.on_event("send_notification_reply_message", (message_id, reply) => {
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
                message_view.narrow_by_topic(message_id, {trigger: "desktop_notification_reply"});
            } else {
                message_view.narrow_by_recipient(message_id, {
                    trigger: "desktop_notification_reply",
                });
            }
        }

        function error(error) {
            electron_bridge.send_event("send_notification_reply_message_failed", {
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

    $(document).on("click", "#open-self-hosted-billing", (event) => {
        event.preventDefault();

        const url = "/json/self-hosted-billing";

        channel.get({
            url,
            success(data) {
                window.open(data.billing_access_url, "_blank", "noopener,noreferrer");
            },
            error(xhr) {
                if (xhr.responseJSON?.msg) {
                    feedback_widget.show({
                        populate($container) {
                            $container.text(xhr.responseJSON.msg);
                        },
                        title_text: $t({defaultMessage: "Error"}),
                    });
                }
            },
        });
    });
}
