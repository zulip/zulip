import $ from "jquery";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_send_later_modal_options from "../templates/send_later_modal_options.hbs";

import * as channel from "./channel";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as compose_banner from "./compose_banner";
import * as compose_ui from "./compose_ui";
import {$t} from "./i18n";
import * as narrow from "./narrow";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as sub_store from "./sub_store";
import * as timerender from "./timerender";

export const MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS = 5 * 60;
export const SCHEDULING_MODAL_UPDATE_INTERVAL_IN_MILLISECONDS = 60 * 1000;

// scheduled_messages_data is a dictionary where key=scheduled_message_id and value=scheduled_messages
export const scheduled_messages_data = {};

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

export function is_send_later_timestamp_missing_or_expired(
    timestamp_in_seconds,
    current_time_in_seconds,
) {
    if (!timestamp_in_seconds) {
        return true;
    }
    // Determine if the selected timestamp is less than the minimum
    // scheduled message delay
    if (timestamp_in_seconds - current_time_in_seconds < MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS) {
        return true;
    }
    return false;
}

function hide_scheduled_message_success_compose_banner(scheduled_message_id) {
    $(
        `.message_scheduled_success_compose_banner[data-scheduled-message-id=${scheduled_message_id}]`,
    ).hide();
}

export function add_scheduled_messages(scheduled_messages) {
    for (const scheduled_message of scheduled_messages) {
        scheduled_messages_data[scheduled_message.scheduled_message_id] = scheduled_message;
    }
}

export function remove_scheduled_message(scheduled_message_id) {
    if (scheduled_messages_data[scheduled_message_id] !== undefined) {
        delete scheduled_messages_data[scheduled_message_id];
        hide_scheduled_message_success_compose_banner(scheduled_message_id);
    }
}

export function update_scheduled_message(scheduled_message) {
    if (scheduled_messages_data[scheduled_message.scheduled_message_id] === undefined) {
        return;
    }

    scheduled_messages_data[scheduled_message.scheduled_message_id] = scheduled_message;
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
            stream: sub_store.maybe_get_stream_name(scheduled_msg.to),
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

function show_message_unscheduled_banner(scheduled_delivery_timestamp) {
    const deliver_at = timerender.get_full_datetime(
        new Date(scheduled_delivery_timestamp * 1000),
        "time",
    );
    const unscheduled_banner = render_compose_banner({
        banner_type: compose_banner.WARNING,
        banner_text: $t({
            defaultMessage: "This message is no longer scheduled to be sent.",
        }),
        button_text: $t({defaultMessage: "Schedule for {deliver_at}"}, {deliver_at}),
        classname: compose_banner.CLASSNAMES.unscheduled_message,
    });
    compose_banner.append_compose_banner_to_banner_list(unscheduled_banner, $("#compose_banners"));
}

export function edit_scheduled_message(scheduled_message_id, should_narrow_to_recipient = true) {
    const scheduled_msg = scheduled_messages_data[scheduled_message_id];
    delete_scheduled_message(scheduled_message_id, () => {
        open_scheduled_message_in_compose(scheduled_msg, should_narrow_to_recipient);
        show_message_unscheduled_banner(scheduled_msg.scheduled_delivery_timestamp);
    });
}

export function delete_scheduled_message(scheduled_msg_id, success = () => {}) {
    channel.del({
        url: "/json/scheduled_messages/" + scheduled_msg_id,
        success,
    });
}

export function get_count() {
    return Object.keys(scheduled_messages_data).length;
}

export function get_filtered_send_opts(date) {
    const send_times = compute_send_times(date);

    const day = date.getDay(); // Starts with 0 for Sunday.

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

    const minutes_into_day = date.getHours() * 60 + date.getMinutes();
    // Show Today send options based on time of day
    if (minutes_into_day < 9 * 60 - MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS / 60) {
        // Allow Today at 9:00am only up to minimum scheduled message delay
        possible_send_later_today = send_later_today;
    } else if (minutes_into_day < (12 + 4) * 60 - MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS / 60) {
        // Allow Today at 4:00pm only up to minimum scheduled message delay
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
    add_scheduled_messages(scheduled_messages_params.scheduled_messages);

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

// This function is exported for unit testing purposes.
export function should_update_send_later_options(date) {
    const current_minute = date.getMinutes();
    const current_hour = date.getHours();

    if (current_hour === 0 && current_minute === 0) {
        // We need to rerender the available options at midnight,
        // since Monday could become in range.
        return true;
    }

    // Rerender at MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS before the
    // hour, so we don't offer a 4:00PM send time at 3:59 PM.
    return current_minute === 60 - MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS / 60;
}

export function update_send_later_options() {
    const now = new Date();
    if (should_update_send_later_options(now)) {
        const filtered_send_opts = get_filtered_send_opts(now);
        $("#send_later_options").replaceWith(render_send_later_modal_options(filtered_send_opts));
    }
}
