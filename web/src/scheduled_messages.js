import $ from "jquery";

import * as channel from "./channel";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import * as compose_ui from "./compose_ui";
import {$t} from "./i18n";
import * as narrow from "./narrow";
import * as notifications from "./notifications";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as stream_data from "./stream_data";

export let scheduled_messages_data = [];

function sort_scheduled_messages_data() {
    scheduled_messages_data.sort(
        (msg1, msg2) => msg1.scheduled_delivery_timestamp - msg2.scheduled_delivery_timestamp,
    );
}

export function add_scheduled_messages(scheduled_messages) {
    scheduled_messages_data.push(...scheduled_messages);
    sort_scheduled_messages_data();
}

export function remove_scheduled_message(scheduled_message_id) {
    const msg_index = scheduled_messages_data.findIndex(
        (msg) => msg.scheduled_message_id === scheduled_message_id,
    );
    if (msg_index !== undefined) {
        scheduled_messages_data.splice(msg_index, 1);
    }
}

export function update_scheduled_message(scheduled_message) {
    const msg_index = scheduled_messages_data.findIndex(
        (msg) => msg.scheduled_message_id === scheduled_message.scheduled_message_id,
    );

    if (msg_index === undefined) {
        return;
    }

    scheduled_messages_data[msg_index] = scheduled_message;
    sort_scheduled_messages_data();
}

export function open_scheduled_message_in_compose(scheduled_msg) {
    let compose_args;
    if (scheduled_msg.type === "stream") {
        compose_args = {
            type: "stream",
            stream: stream_data.maybe_get_stream_name(scheduled_msg.to),
            topic: scheduled_msg.topic,
            content: scheduled_msg.content,
        };
    } else {
        const recipient_emails = [];
        if (scheduled_msg.to) {
            for (const recipient_id of scheduled_msg.to) {
                recipient_emails.push(people.get_by_user_id(recipient_id).email);
            }
        }
        compose_args = {
            type: scheduled_msg.type,
            private_message_recipient: recipient_emails.join(","),
            content: scheduled_msg.content,
        };
    }

    if (compose_args.type === "stream") {
        narrow.activate(
            [
                {operator: "stream", operand: compose_args.stream},
                {operator: "topic", operand: compose_args.topic},
            ],
            {trigger: "edit scheduled message"},
        );
    } else {
        narrow.activate([{operator: "dm", operand: compose_args.private_message_recipient}], {
            trigger: "edit scheduled message",
        });
    }

    compose.clear_compose_box();
    compose_banner.clear_message_sent_banners(false);
    compose_actions.start(compose_args.type, compose_args);
    compose_ui.autosize_textarea($("#compose-textarea"));
    popover_menus.set_selected_schedule_time(scheduled_msg.scheduled_delivery_timestamp * 1000);
}

export function send_request_to_schedule_message(scheduled_message_data, deliver_at) {
    const success = function () {
        compose.clear_compose_box();
        notifications.notify_above_composebox(
            $t({defaultMessage: `Your message has been scheduled for {deliver_at}.`}, {deliver_at}),
            "scheduled_message_banner",
            "/#scheduled",
            "",
            $t({defaultMessage: "View scheduled messages"}),
        );
    };

    const error = function (xhr) {
        const response = channel.xhr_error_message("Error sending message", xhr);
        compose_ui.hide_compose_spinner();
        compose_banner.show_error_message(
            response,
            compose_banner.CLASSNAMES.generic_compose_error,
            $("#compose-textarea"),
        );
    };

    channel.post({
        url: "/json/scheduled_messages",
        data: scheduled_message_data,
        success,
        error,
    });
}

export function edit_scheduled_message(scheduled_message_id) {
    const scheduled_msg = scheduled_messages_data.find(
        (msg) => msg.scheduled_message_id === scheduled_message_id,
    );
    delete_scheduled_message(scheduled_message_id, () =>
        open_scheduled_message_in_compose(scheduled_msg),
    );
}

export function delete_scheduled_message(scheduled_msg_id, success = () => {}) {
    channel.del({
        url: "/json/scheduled_messages/" + scheduled_msg_id,
        success,
    });
}

export function initialize() {
    if (scheduled_messages_data.length === 0) {
        scheduled_messages_data = page_params.scheduled_messages;
    } else {
        add_scheduled_messages(page_params.scheduled_messages);
    }
}
