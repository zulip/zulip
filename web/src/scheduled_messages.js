import $ from "jquery";

import render_success_message_scheduled_banner from "../templates/compose_banner/success_message_scheduled_banner.hbs";

import * as channel from "./channel";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import * as compose_ui from "./compose_ui";
import * as drafts from "./drafts";
import {$t} from "./i18n";
import * as narrow from "./narrow";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";

export let scheduled_messages_data = [];

function compute_send_times(now = new Date()) {
    const send_times = {};

    const today = new Date(now);
    const tomorrow = new Date(new Date(now).setDate(now.getDate() + 1));
    // Find the next Monday by subtracting the current day (0-6) from 8
    const monday = new Date(new Date(now).setDate(now.getDate() + 8 - now.getDay()));

    // Since setHours returns a timestamp, it's safe to mutate the
    // original date objects here.
    //
    // today at 9am
    send_times.today_nine_am = today.setHours(9, 0, 0, 0);
    // today at 4pm
    send_times.today_four_pm = today.setHours(16, 0, 0, 0);
    // tomorrow at 9am
    send_times.tomorrow_nine_am = tomorrow.setHours(9, 0, 0, 0);
    // tomorrow at 4pm
    send_times.tomorrow_four_pm = tomorrow.setHours(16, 0, 0, 0);
    // next Monday at 9am
    send_times.monday_nine_am = monday.setHours(9, 0, 0, 0);
    return send_times;
}

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

function narrow_via_edit_scheduled_message(compose_args) {
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
}

export function open_scheduled_message_in_compose(scheduled_msg, should_narrow_to_recipient) {
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

    if (should_narrow_to_recipient) {
        narrow_via_edit_scheduled_message(compose_args);
    }

    compose.clear_compose_box();
    compose_banner.clear_message_sent_banners(false);
    compose_actions.start(compose_args.type, compose_args);
    compose_ui.autosize_textarea($("#compose-textarea"));
    popover_menus.set_selected_schedule_timestamp(scheduled_msg.scheduled_delivery_timestamp);
}

export function send_request_to_schedule_message(scheduled_message_data, deliver_at) {
    const $banner_container = $("#compose_banners");
    const success = function (data) {
        drafts.draft_model.deleteDraft($("#compose-textarea").data("draft-id"));
        compose.clear_compose_box();
        const new_row = render_success_message_scheduled_banner({
            scheduled_message_id: data.scheduled_message_id,
            deliver_at,
        });
        compose_banner.clear_message_sent_banners();
        compose_banner.append_compose_banner_to_banner_list(new_row, $banner_container);
    };

    const error = function (xhr) {
        const response = channel.xhr_error_message("Error sending message", xhr);
        compose_ui.hide_compose_spinner();
        compose_banner.show_error_message(
            response,
            compose_banner.CLASSNAMES.generic_compose_error,
            $banner_container,
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

export function edit_scheduled_message(scheduled_message_id, should_narrow_to_recipient = true) {
    const scheduled_msg = scheduled_messages_data.find(
        (msg) => msg.scheduled_message_id === scheduled_message_id,
    );
    delete_scheduled_message(scheduled_message_id, () =>
        open_scheduled_message_in_compose(scheduled_msg, should_narrow_to_recipient),
    );
}

export function delete_scheduled_message(scheduled_msg_id, success = () => {}) {
    channel.del({
        url: "/json/scheduled_messages/" + scheduled_msg_id,
        success,
    });
}

export function get_count() {
    return scheduled_messages_data.length;
}

export function get_filtered_send_opts(date) {
    const send_times = compute_send_times(date);

    const day = date.getDay(); // Starts with 0 for Sunday.
    const hours = date.getHours();

    const send_later_today = {
        today_nine_am: {
            text: $t(
                {defaultMessage: "Today at {time}"},
                {
                    time: timerender.get_localized_date_or_time_for_format(
                        send_times.today_nine_am,
                        "time",
                    ),
                },
            ),
            stamp: send_times.today_nine_am,
        },
        today_four_pm: {
            text: $t(
                {defaultMessage: "Today at {time}"},
                {
                    time: timerender.get_localized_date_or_time_for_format(
                        send_times.today_four_pm,
                        "time",
                    ),
                },
            ),
            stamp: send_times.today_four_pm,
        },
    };

    const send_later_tomorrow = {
        tomorrow_nine_am: {
            text: $t(
                {defaultMessage: "Tomorrow at {time}"},
                {
                    time: timerender.get_localized_date_or_time_for_format(
                        send_times.tomorrow_nine_am,
                        "time",
                    ),
                },
            ),
            stamp: send_times.tomorrow_nine_am,
        },
        tomorrow_four_pm: {
            text: $t(
                {defaultMessage: "Tomorrow at {time}"},
                {
                    time: timerender.get_localized_date_or_time_for_format(
                        send_times.tomorrow_four_pm,
                        "time",
                    ),
                },
            ),
            stamp: send_times.tomorrow_four_pm,
        },
    };

    const send_later_monday = {
        monday_nine_am: {
            text: $t(
                {defaultMessage: "Monday at {time}"},
                {
                    time: timerender.get_localized_date_or_time_for_format(
                        send_times.monday_nine_am,
                        "time",
                    ),
                },
            ),
            stamp: send_times.monday_nine_am,
        },
    };

    const send_later_custom = {
        text: $t({defaultMessage: "Custom"}),
    };

    let possible_send_later_today = {};
    let possible_send_later_monday = {};
    if (hours <= 8) {
        possible_send_later_today = send_later_today;
    } else if (hours <= 15) {
        possible_send_later_today.today_four_pm = send_later_today.today_four_pm;
    } else {
        possible_send_later_today = false;
    }
    // Show send_later_monday options only on Fridays and Saturdays.
    if (day >= 5) {
        possible_send_later_monday = send_later_monday;
    } else {
        possible_send_later_monday = false;
    }

    return {
        possible_send_later_today,
        send_later_tomorrow,
        possible_send_later_monday,
        send_later_custom,
    };
}

export function initialize(scheduled_messages_params) {
    scheduled_messages_data = scheduled_messages_params.scheduled_messages;

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
