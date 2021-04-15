import $ from "jquery";

import * as message_lists from "./message_lists";

function update_reply_recipient_label() {
    const message = message_lists.current.selected_message();
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

// TODO: Move the closed-compose buttons click handlers here, probably.

export function initialize() {
    // When the message selection changes, change the label on the Reply button.
    $(document).on("message_selected.zulip", () => {
        update_reply_recipient_label();
    });
}
