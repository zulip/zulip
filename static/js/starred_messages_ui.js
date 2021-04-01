import $ from "jquery";

import render_confirm_unstar_all_messages from "../templates/confirm_unstar_all_messages.hbs";
import render_confirm_unstar_all_messages_in_topic from "../templates/confirm_unstar_all_messages_in_topic.hbs";

import * as confirm_dialog from "./confirm_dialog";
import {i18n} from "./i18n";
import * as message_flags from "./message_flags";

export function confirm_unstar_all_messages() {
    const modal_parent = $(".left-sidebar-modal-holder");
    const html_body = render_confirm_unstar_all_messages();

    confirm_dialog.launch({
        parent: modal_parent,
        html_heading: i18n.t("Unstar all messages"),
        html_body,
        html_yes_button: i18n.t("Unstar messages"),
        on_click: message_flags.unstar_all_messages,
    });
}

export function confirm_unstar_all_messages_in_topic(stream_id, topic) {
    function on_click() {
        message_flags.unstar_all_messages_in_topic(stream_id, topic);
    }

    const modal_parent = $(".left-sidebar-modal-holder");
    const html_body = render_confirm_unstar_all_messages_in_topic({
        topic,
    });

    confirm_dialog.launch({
        parent: modal_parent,
        html_heading: i18n.t("Unstar messages in topic"),
        html_body,
        html_yes_button: i18n.t("Unstar messages"),
        on_click,
    });
}
