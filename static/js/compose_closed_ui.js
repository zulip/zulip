import $ from "jquery";

import * as compose_actions from "./compose_actions";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as popovers from "./popovers";

function set_reply_button_label(label) {
    $(".compose_reply_button_label").text(label);
}

export function set_standard_text_for_reply_button() {
    set_reply_button_label($t({defaultMessage: "Compose message"}));
}

export function update_reply_recipient_label(message) {
    message = message || message_lists.current.selected_message();
    let recipient_label = "";
    if (message) {
        if (message.stream && message.topic) {
            recipient_label = "#" + message.stream + " > " + message.topic;
        } else if (message.display_reply_to) {
            recipient_label = message.display_reply_to;
        }
    }
    set_reply_button_label($t({defaultMessage: "Message {recipient_label}"}, {recipient_label}));
}

export function initialize() {
    // When the message selection changes, change the label on the Reply button.
    $(document).on("message_selected.zulip", () => {
        update_reply_recipient_label();
    });

    // Click handlers for buttons in the compose compose box.
    $("body").on("click", ".compose_stream_button", () => {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start("stream", {trigger: "new topic button"});
    });

    $("body").on("click", ".compose_private_button", () => {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start("private");
    });

    $("body").on("click", ".compose_mobile_stream_button", () => {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start("stream", {trigger: "new topic button"});
    });

    $("body").on("click", ".compose_mobile_private_button", () => {
        popovers.hide_mobile_message_buttons_popover();
        compose_actions.start("private");
    });

    $("body").on("click", ".compose_reply_button", () => {
        compose_actions.respond_to_message({trigger: "reply button"});
    });
}
