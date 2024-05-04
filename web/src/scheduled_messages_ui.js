import $ from "jquery";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";

import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import {$t} from "./i18n";
import * as narrow from "./narrow";
import * as people from "./people";
import * as scheduled_messages from "./scheduled_messages";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";

export function hide_scheduled_message_success_compose_banner(scheduled_message_id) {
    $(
        `.message_scheduled_success_compose_banner[data-scheduled-message-id=${scheduled_message_id}]`,
    ).hide();
}

function narrow_via_edit_scheduled_message(compose_args) {
    if (compose_args.message_type === "stream") {
        narrow.activate(
            [
                {
                    operator: "channel",
                    operand: stream_data.get_stream_name_from_id(compose_args.stream_id),
                },
                {operator: "topic", operand: compose_args.topic},
            ],
            {trigger: "edit scheduled message"},
        );
    } else {
        narrow.activate([{operator: "dm", operand: compose_args.private_message_recipient}], {
            trigger: "edit scheduled message",
        });
    }
}

export function open_scheduled_message_in_compose(scheduled_msg, should_narrow_to_recipient) {
    let compose_args;
    if (scheduled_msg.type === "stream") {
        compose_args = {
            message_type: "stream",
            stream_id: scheduled_msg.to,
            topic: scheduled_msg.topic,
            content: scheduled_msg.content,
        };
    } else {
        const recipient_emails = [];
        if (scheduled_msg.to) {
            for (const recipient_id of scheduled_msg.to) {
                const recipient_user = people.get_by_user_id(recipient_id);
                if (!recipient_user.is_inaccessible_user) {
                    recipient_emails.push(recipient_user.email);
                }
            }
        }
        compose_args = {
            message_type: scheduled_msg.type,
            private_message_recipient: recipient_emails.join(","),
            content: scheduled_msg.content,
            keep_composebox_empty: true,
        };
    }

    if (should_narrow_to_recipient) {
        narrow_via_edit_scheduled_message(compose_args);
    }

    compose_actions.start(compose_args);
    scheduled_messages.set_selected_schedule_timestamp(scheduled_msg.scheduled_delivery_timestamp);
}

function show_message_unscheduled_banner(scheduled_delivery_timestamp) {
    const deliver_at = timerender.get_full_datetime(
        new Date(scheduled_delivery_timestamp * 1000),
        "time",
    );
    const unscheduled_banner_html = render_compose_banner({
        banner_type: compose_banner.WARNING,
        banner_text: $t({
            defaultMessage: "This message is no longer scheduled to be sent.",
        }),
        button_text: $t({defaultMessage: "Schedule for {deliver_at}"}, {deliver_at}),
        classname: compose_banner.CLASSNAMES.unscheduled_message,
    });
    compose_banner.append_compose_banner_to_banner_list(
        $(unscheduled_banner_html),
        $("#compose_banners"),
    );
}

export function edit_scheduled_message(scheduled_message_id, should_narrow_to_recipient = true) {
    const scheduled_msg = scheduled_messages.scheduled_messages_data.get(scheduled_message_id);
    scheduled_messages.delete_scheduled_message(scheduled_message_id, () => {
        open_scheduled_message_in_compose(scheduled_msg, should_narrow_to_recipient);
        show_message_unscheduled_banner(scheduled_msg.scheduled_delivery_timestamp);
    });
}

export function initialize() {
    $("body").on("click", ".undo_scheduled_message", (e) => {
        const scheduled_message_id = Number.parseInt(
            $(e.target)
                .parents(".message_scheduled_success_compose_banner")
                .attr("data-scheduled-message-id"),
            10,
        );
        const should_narrow_to_recipient = false;
        edit_scheduled_message(scheduled_message_id, should_narrow_to_recipient);
        e.preventDefault();
        e.stopPropagation();
    });
}
