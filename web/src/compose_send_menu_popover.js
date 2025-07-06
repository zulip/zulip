import $ from "jquery";
import * as tippy from "tippy.js";

import render_schedule_message_popover from "../templates/popovers/schedule_message_popover.hbs";
import render_send_later_popover from "../templates/popovers/send_later_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose from "./compose.js";
import * as compose_state from "./compose_state.ts";
import * as compose_validate from "./compose_validate.ts";
import * as drafts from "./drafts.ts";
import * as flatpickr from "./flatpickr.ts";
import * as message_reminder from "./message_reminder.ts";
import * as popover_menus from "./popover_menus.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

export const SCHEDULING_MODAL_UPDATE_INTERVAL_IN_MILLISECONDS = 60 * 1000;
const ENTER_SENDS_SELECTION_DELAY = 600;

let send_later_popover_keyboard_toggle = false;

function set_compose_box_schedule(element) {
    const selected_send_at_time = element.dataset.sendStamp / 1000;
    return selected_send_at_time;
}

export function open_schedule_message_menu(
    remind_message_id = undefined,
    target = "#send_later i",
) {
    if (remind_message_id === undefined && !compose_validate.validate(true)) {
        return;
    }
    let interval;
    const message_schedule_callback = (time) => {
        if (remind_message_id !== undefined) {
            do_schedule_reminder(time, remind_message_id);
        } else {
            do_schedule_message(time);
        }
    };

    popover_menus.toggle_popover_menu(target, {
        theme: "popover-menu",
        placement: remind_message_id !== undefined ? "bottom" : "top",
        popperOptions: {
            modifiers: [
                {
                    name: "flip",
                    options: {
                        fallbackPlacements:
                            remind_message_id !== undefined ? ["top", "left"] : ["bottom", "left"],
                    },
                },
            ],
        },
        onShow(instance) {
            // Only show send later options that are possible today.
            const date = new Date();
            const filtered_send_opts = scheduled_messages.get_filtered_send_opts(date);
            instance.setContent(
                parse_html(
                    render_schedule_message_popover({
                        ...filtered_send_opts,
                        is_reminder: remind_message_id !== undefined,
                    }),
                ),
            );
            popover_menus.popover_instances.send_later_options = instance;

            interval = setInterval(
                update_send_later_options,
                SCHEDULING_MODAL_UPDATE_INTERVAL_IN_MILLISECONDS,
            );
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.on("click", ".send_later_custom", (e) => {
                const $send_later_options_content = $popper.find(".popover-menu-list");
                const current_time = new Date();
                flatpickr.show_flatpickr(
                    $(".send_later_custom")[0],
                    (send_at_time) => {
                        message_schedule_callback(send_at_time);
                        popover_menus.hide_current_popover_if_visible(instance);
                    },
                    new Date(current_time.getTime() + 60 * 60 * 1000),
                    {
                        minDate: new Date(
                            current_time.getTime() +
                                scheduled_messages.MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS * 1000,
                        ),
                        onClose(selectedDates, _dateStr, instance) {
                            // Return to normal state.
                            $send_later_options_content.css("pointer-events", "all");
                            const selected_date = selectedDates[0];

                            if (selected_date && selected_date < instance.config.minDate) {
                                scheduled_messages.set_minimum_scheduled_message_delay_minutes_note(
                                    true,
                                );
                            } else {
                                scheduled_messages.set_minimum_scheduled_message_delay_minutes_note(
                                    false,
                                );
                            }
                        },
                    },
                );
                // Disable interaction with rest of the options in the popover.
                $send_later_options_content.css("pointer-events", "none");
                e.preventDefault();
                e.stopPropagation();
            });
            $popper.one(
                "click",
                ".send_later_today, .send_later_tomorrow, .send_later_monday",
                (e) => {
                    const send_at_time = set_compose_box_schedule(e.currentTarget);
                    message_schedule_callback(send_at_time);
                    e.preventDefault();
                    e.stopPropagation();
                    popover_menus.hide_current_popover_if_visible(instance);
                },
            );
        },
        onHidden(instance) {
            clearInterval(interval);
            instance.destroy();
            popover_menus.popover_instances.send_later_options = undefined;
        },
    });
}

function parse_sent_at_time(send_at_time) {
    if (!Number.isInteger(send_at_time)) {
        // Convert to timestamp if this is not a timestamp.
        return Math.floor(Date.parse(send_at_time) / 1000);
    }
    return send_at_time;
}

export function do_schedule_message(send_at_time) {
    send_at_time = parse_sent_at_time(send_at_time);
    scheduled_messages.set_selected_schedule_timestamp(send_at_time);
    compose.finish(true);
}

export function do_schedule_reminder(send_at_time, remind_message_id) {
    send_at_time = parse_sent_at_time(send_at_time);
    message_reminder.set_message_reminder(send_at_time, remind_message_id);
}

function get_send_later_menu_items() {
    const $send_later_options = $("#send_later_popover");
    if ($send_later_options.length === 0) {
        blueslip.error("Trying to get menu items when schedule popover is closed.");
        return undefined;
    }

    return $send_later_options.find("[tabindex='0']");
}

function focus_first_send_later_popover_item() {
    // It is recommended to only call this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_send_later_menu_items();
    popover_menus.focus_first_popover_item($items);
}

export function toggle() {
    send_later_popover_keyboard_toggle = true;
    $("#send_later i").trigger("click");
}

export function initialize() {
    tippy.delegate("body", {
        ...popover_menus.default_popover_props,
        theme: "popover-menu",
        target: "#send_later i",
        onUntrigger() {
            // This is only called when the popover is closed by clicking on `target`.
            $("textarea#compose-textarea").trigger("focus");
        },
        onShow(instance) {
            const formatted_send_later_time =
                scheduled_messages.get_formatted_selected_send_later_time();
            // If there's existing text in the composebox, show an option
            // to keep/save the current draft and start a new message.
            const show_compose_new_message = compose_state.has_savable_message_content();
            instance.setContent(
                parse_html(
                    render_send_later_popover({
                        enter_sends_true: user_settings.enter_sends,
                        formatted_send_later_time,
                        show_compose_new_message,
                    }),
                ),
            );
            popover_menus.popover_instances.send_later = instance;
        },
        onMount(instance) {
            if (send_later_popover_keyboard_toggle) {
                focus_first_send_later_popover_item();
                send_later_popover_keyboard_toggle = false;
            }
            // Make sure the compose drafts count, which is also displayed in this popover, has a current value.
            drafts.update_compose_draft_count();
            const $popper = $(instance.popper);
            $popper.one("click", ".send_later_selected_send_later_time", () => {
                const send_at_timestamp = scheduled_messages.get_selected_send_later_timestamp();
                do_schedule_message(send_at_timestamp);
                popover_menus.hide_current_popover_if_visible(instance);
            });
            // Handle clicks on Enter-to-send settings
            $popper.one("click", ".enter_sends_choice", (e) => {
                let selected_behaviour = $(e.currentTarget)
                    .find("input[type='radio']")
                    .attr("value");
                selected_behaviour = selected_behaviour === "true"; // Convert to bool
                user_settings.enter_sends = selected_behaviour;

                channel.patch({
                    url: "/json/settings",
                    data: {enter_sends: selected_behaviour},
                });
                e.stopPropagation();
                setTimeout(() => {
                    popover_menus.hide_current_popover_if_visible(instance);
                    // Refocus in the content box so you can continue typing or
                    // press Enter to send.
                    $("textarea#compose-textarea").trigger("focus");
                }, ENTER_SENDS_SELECTION_DELAY);
            });
            // Handle Send later clicks
            $popper.one("click", ".open_send_later_modal", () => {
                popover_menus.hide_current_popover_if_visible(instance);
                open_schedule_message_menu();
            });
            $popper.one("click", ".compose_new_message", () => {
                drafts.update_draft();
                // If they want to compose a new message instead
                // of seeing the draft, remember this and don't
                // restore drafts in this narrow until the user
                // switches narrows. This allows a user to send
                // a bunch of messages in a conversation without
                // clicking the "start a new draft" button every
                // time.
                compose_state.prevent_draft_restoring();
                compose.clear_compose_box();
                compose.clear_preview_area();
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.send_later = undefined;
            send_later_popover_keyboard_toggle = false;
        },
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
    return current_minute === 60 - scheduled_messages.MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS / 60;
}

export function update_send_later_options() {
    const now = new Date();
    if (should_update_send_later_options(now)) {
        const filtered_send_opts = scheduled_messages.get_filtered_send_opts(now);
        $("#send-later-options").replaceWith(
            $(render_schedule_message_popover(filtered_send_opts)),
        );
    }
}
