import $ from "jquery";

import * as compose_actions from "./compose_actions";
import * as message_lists from "./message_lists";
import * as popovers from "./popovers";

export function hide_reply_button() {
    $(".reply_button_container").hide();
    $("#compose_buttons").css("justify-content", "flex-end");
}

export function show_reply_button() {
    $(".reply_button_container").show();
    $("#compose_buttons").css("justify-content", "flex-start");
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
    $(".compose_reply_button_recipient_label").text(recipient_label);
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
