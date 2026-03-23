import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_schedule_message_popover from "../templates/popovers/schedule_message_popover.hbs";
import render_send_later_popover from "../templates/popovers/send_later_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose from "./compose.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_validate from "./compose_validate.ts";
import * as drafts from "./drafts.ts";
import * as flatpickr from "./flatpickr.ts";
import * as input_pill from "./input_pill.ts";
import {$t} from "./i18n.ts";
import * as message_reminder from "./message_reminder.ts";
import * as pill_typeahead from "./pill_typeahead.ts";
import * as popover_menus from "./popover_menus.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as stream_pill from "./stream_pill.ts";
import * as user_pill from "./user_pill.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

export const SCHEDULING_MODAL_UPDATE_INTERVAL_IN_MILLISECONDS = 60 * 1000;
const ENTER_SENDS_SELECTION_DELAY = 600;

let send_later_popover_keyboard_toggle = false;

function set_recurring_builder_feedback(
    $feedback: JQuery,
    state: "error" | "success",
    message: string,
): void {
    $feedback.removeClass("recurring-feedback-error recurring-feedback-success");
    $feedback.addClass(
        state === "error" ? "recurring-feedback-error" : "recurring-feedback-success",
    );
    $feedback.text(message);
}

function create_stream_pill_item(
    stream_name: string,
    current_items: stream_pill.StreamPill[],
): stream_pill.StreamPill | undefined {
    const stream_prefix_required = false;
    return stream_pill.create_item_from_stream_name(
        stream_name,
        current_items,
        stream_prefix_required,
    );
}

function get_ordinal_day_label(day: number): string {
    const remainder_hundred = day % 100;
    if (remainder_hundred >= 11 && remainder_hundred <= 13) {
        return `${day}th`;
    }

    switch (day % 10) {
        case 1:
            return `${day}st`;
        case 2:
            return `${day}nd`;
        case 3:
            return `${day}rd`;
        default:
            return `${day}th`;
    }
}

function get_monthly_day_option_label(day: number): string {
    return get_ordinal_day_label(day);
}

function get_monthly_ordinal_label(ordinal: string): string {
    switch (ordinal) {
        case "first":
            return $t({defaultMessage: "first"});
        case "second":
            return $t({defaultMessage: "second"});
        case "third":
            return $t({defaultMessage: "third"});
        case "fourth":
            return $t({defaultMessage: "fourth"});
        case "last":
            return $t({defaultMessage: "last"});
        default:
            return ordinal;
    }
}

function get_monthly_weekday_label(weekday: string): string {
    switch (weekday) {
        case "MO":
            return $t({defaultMessage: "Monday"});
        case "TU":
            return $t({defaultMessage: "Tuesday"});
        case "WE":
            return $t({defaultMessage: "Wednesday"});
        case "TH":
            return $t({defaultMessage: "Thursday"});
        case "FR":
            return $t({defaultMessage: "Friday"});
        case "SA":
            return $t({defaultMessage: "Saturday"});
        case "SU":
            return $t({defaultMessage: "Sunday"});
        default:
            return weekday;
    }
}

function initialize_recurring_builder($popper: JQuery): void {
    if ($popper.data("recurring-builder-initialized") === true) {
        return;
    }
    const $feedback = $popper.find(".recurring-builder-feedback");
    const $channel_pill_container = $popper.find(".recurring-channels-pill-container");
    const $dm_pill_container = $popper.find(".recurring-users-pill-container");
    if ($channel_pill_container.length === 0 || $dm_pill_container.length === 0) {
        return;
    }
    $popper.data("recurring-builder-initialized", true);

    const channel_pills = input_pill.create<stream_pill.StreamPill>({
        $container: $channel_pill_container,
        create_item_from_text: create_stream_pill_item,
        get_text_from_item: stream_pill.get_stream_name_from_item,
        get_display_value_from_item: stream_pill.get_display_value_from_item,
        generate_pill_html: stream_pill.generate_pill_html,
    });
    pill_typeahead.set_up_stream($channel_pill_container.find(".input"), channel_pills, {
        help_on_empty_strings: true,
        hide_on_empty_after_backspace: true,
    });

    const dm_pills = user_pill.create_pills($dm_pill_container, {
        exclude_inaccessible_users: true,
    });
    pill_typeahead.set_up_user($dm_pill_container.find(".input"), dm_pills, {});
    const $frequency = $popper.find(".recurring-frequency-input");
    const $weekly_options = $popper.find(".recurring-weekly-options");
    const $monthly_options = $popper.find(".recurring-monthly-options");
    const $monthday_input = $popper.find(".recurring-monthday-input");
    const $monthly_ordinal_input = $popper.find(".recurring-monthly-ordinal-input");
    const $monthly_weekday_input = $popper.find(".recurring-monthly-weekday-input");
    const $monthly_mode_inputs = $popper.find<HTMLInputElement>(".recurring-monthly-mode");
    const $short_month_note = $popper.find(".recurring-short-month-note");
    const $monthly_summary = $popper.find(".recurring-monthly-summary");

    for (let day = 1; day <= 31; day += 1) {
        $monthday_input.append(
            $("<option></option>").attr("value", day).text(get_monthly_day_option_label(day)),
        );
    }
    $monthday_input.val("1");

    for (const ordinal of ["first", "second", "third", "fourth", "last"]) {
        $monthly_ordinal_input.append(
            $("<option></option>").attr("value", ordinal).text(get_monthly_ordinal_label(ordinal)),
        );
    }
    $monthly_ordinal_input.val("first");

    for (const weekday of ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]) {
        $monthly_weekday_input.append(
            $("<option></option>").attr("value", weekday).text(get_monthly_weekday_label(weekday)),
        );
    }
    $monthly_weekday_input.val("MO");

    const get_selected_monthly_mode = (): string =>
        String($monthly_mode_inputs.filter(":checked").first().val() ?? "day");

    const refresh_monthly_selector = (): void => {
        const selected_monthly_mode = get_selected_monthly_mode();
        const use_day_selector = selected_monthly_mode === "day";
        const use_weekday_selector = selected_monthly_mode === "weekday";
        $monthday_input.prop("disabled", !use_day_selector);
        $monthly_ordinal_input.prop("disabled", !use_weekday_selector);
        $monthly_weekday_input.prop("disabled", !use_weekday_selector);

        const selected_monthday = Number($monthday_input.val());
        $short_month_note.toggleClass(
            "recurring-hidden",
            !(selected_monthly_mode === "day" && selected_monthday >= 29),
        );
    };

    const refresh_monthly_summary = (): void => {
        const selected_monthly_mode = get_selected_monthly_mode();
        let summary = "";

        if (selected_monthly_mode === "last_day") {
            summary = $t({defaultMessage: "Repeats on the last day of every month."});
        } else if (selected_monthly_mode === "weekday") {
            const ordinal = String($monthly_ordinal_input.val() ?? "first");
            const weekday = String($monthly_weekday_input.val() ?? "MO");
            summary = $t(
                {defaultMessage: "Repeats on the {ordinal} {weekday} of every month."},
                {
                    ordinal: get_monthly_ordinal_label(ordinal),
                    weekday: get_monthly_weekday_label(weekday),
                },
            );
        } else {
            const selected_monthday = Number($monthday_input.val());
            summary = $t(
                {defaultMessage: "Repeats on the {day} of every month."},
                {day: get_ordinal_day_label(selected_monthday)},
            );
        }

        $monthly_summary.text(summary);
    };

    const refresh_custom_options = (): void => {
        const recurrence = $frequency.val();
        $weekly_options.toggleClass("recurring-hidden", recurrence !== "weekly");
        $monthly_options.toggleClass("recurring-hidden", recurrence !== "monthly");
    };
    refresh_custom_options();
    refresh_monthly_selector();
    refresh_monthly_summary();
    $frequency.on("change", refresh_custom_options);
    $monthly_mode_inputs.on("change", () => {
        refresh_monthly_selector();
        refresh_monthly_summary();
    });
    $monthday_input.on("change", () => {
        refresh_monthly_selector();
        refresh_monthly_summary();
    });
    $monthly_ordinal_input.on("change", refresh_monthly_summary);
    $monthly_weekday_input.on("change", refresh_monthly_summary);

    $popper.on("click", ".validate-recurring-draft", (e) => {
        const recurrence = $popper.find(".recurring-frequency-input").val();
        const send_time = $popper.find(".recurring-time-input").val();
        const selected_stream_ids = stream_pill.get_stream_ids(channel_pills);
        const selected_user_ids = user_pill.get_user_ids(dm_pills);
        const selected_weekdays = $popper.find(".recurring-weekday:checked").length;
        const selected_monthly_mode = get_selected_monthly_mode();
        const selected_monthday = $monthday_input.val();
        const selected_monthly_ordinal = $monthly_ordinal_input.val();
        const selected_monthly_weekday = $monthly_weekday_input.val();

        if (
            recurrence === undefined ||
            recurrence === "" ||
            send_time === undefined ||
            send_time === ""
        ) {
            set_recurring_builder_feedback(
                $feedback,
                "error",
                $t({defaultMessage: "Select a recurrence and time."}),
            );
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        if (selected_stream_ids.length === 0 && selected_user_ids.length === 0) {
            set_recurring_builder_feedback(
                $feedback,
                "error",
                $t({defaultMessage: "Add at least one destination (channel or direct message)."}),
            );
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        if (recurrence === "weekly" && selected_weekdays === 0) {
            set_recurring_builder_feedback(
                $feedback,
                "error",
                $t({defaultMessage: "For weekly recurrence, choose at least one day."}),
            );
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        if (
            recurrence === "monthly" &&
            selected_monthly_mode === "day" &&
            (selected_monthday === undefined || selected_monthday === "")
        ) {
            set_recurring_builder_feedback(
                $feedback,
                "error",
                $t({defaultMessage: "For monthly recurrence, choose a day of the month."}),
            );
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        if (
            recurrence === "monthly" &&
            selected_monthly_mode === "weekday" &&
            (selected_monthly_ordinal === undefined ||
                selected_monthly_ordinal === "" ||
                selected_monthly_weekday === undefined ||
                selected_monthly_weekday === "")
        ) {
            set_recurring_builder_feedback(
                $feedback,
                "error",
                $t({defaultMessage: "For monthly recurrence, choose a weekday rule."}),
            );
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        set_recurring_builder_feedback(
            $feedback,
            "success",
            $t(
                {
                    defaultMessage:
                        "Recurring draft looks valid ({channel_count} channel(s), {user_count} user(s)).",
                },
                {
                    channel_count: selected_stream_ids.length,
                    user_count: selected_user_ids.length,
                },
            ),
        );
        e.preventDefault();
        e.stopPropagation();
    });
}

function set_compose_box_schedule(element: HTMLElement): number {
    const send_stamp = element.getAttribute("data-send-stamp");
    assert(send_stamp !== null);
    const selected_send_at_time = Number.parseInt(send_stamp, 10) / 1000;
    return selected_send_at_time;
}

export function open_schedule_message_menu(
    remind_message_id: number | undefined,
    target: tippy.ReferenceElement,
): void {
    if (remind_message_id === undefined && !compose_validate.validate(true)) {
        return;
    }
    let interval: ReturnType<typeof setTimeout>;

    popover_menus.toggle_popover_menu(target, {
        theme: "popover-menu",
        placement: remind_message_id !== undefined ? "bottom" : "top",
        hideOnClick: false,
        onClickOutside(instance, event) {
            const clicked_in_typeahead =
                $(event.target as HTMLElement).closest(".typeahead.dropdown-menu").length > 0;
            if (clicked_in_typeahead) {
                return;
            }
            instance.hide();
        },
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
            if (remind_message_id !== undefined) {
                // Maintain the vdots visibility, as when the message
                // actions menu is open
                $(instance.reference).closest(".message_row").addClass("has_actions_popover");
                popover_menus.focus_first_popover_item(
                    popover_menus.get_popover_items_for_instance(instance),
                );
            }
            const $popper = $(instance.popper);
            if (remind_message_id === undefined) {
                initialize_recurring_builder($popper);
            }
            const message_schedule_callback = (time: string | number): void => {
                if (remind_message_id !== undefined) {
                    do_schedule_reminder(
                        time,
                        remind_message_id,
                        $popper.find<HTMLTextAreaElement>("textarea.schedule-reminder-note").val()!,
                    );
                } else {
                    do_schedule_message(time);
                }
            };
            $popper.on("click", ".send_later_custom", (e) => {
                const $send_later_options_content = $popper.find(".popover-menu-list");
                const current_time = new Date();
                flatpickr.show_flatpickr(
                    util.the($(".send_later_custom")),
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
                            assert(instance.config.minDate !== undefined);
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
                function (this: HTMLElement, e) {
                    const send_at_time = set_compose_box_schedule(this);
                    message_schedule_callback(send_at_time);
                    e.preventDefault();
                    e.stopPropagation();
                    popover_menus.hide_current_popover_if_visible(instance);
                },
            );
        },
        onHidden(instance) {
            if (remind_message_id !== undefined) {
                // Hide the vdots
                $(instance.reference).closest(".message_row").removeClass("has_actions_popover");
            }
            clearInterval(interval);
            instance.destroy();
            popover_menus.popover_instances.send_later_options = null;
        },
    });
}

function parse_sent_at_time(send_at_time: string | number): number {
    if (typeof send_at_time !== "number") {
        // Convert to timestamp if this is not a timestamp.
        return Math.floor(Date.parse(send_at_time) / 1000);
    }
    return send_at_time;
}

export function do_schedule_message(send_at_time: string | number): void {
    send_at_time = parse_sent_at_time(send_at_time);
    scheduled_messages.set_selected_schedule_timestamp(send_at_time);
    compose.finish(true);
}

export function do_schedule_reminder(
    send_at_time: string | number,
    remind_message_id: number,
    note_text: string,
): void {
    send_at_time = parse_sent_at_time(send_at_time);
    message_reminder.set_message_reminder(send_at_time, remind_message_id, note_text);
}

function get_send_later_menu_items(): JQuery | undefined {
    const $send_later_options = $("#send_later_popover");
    if ($send_later_options.length === 0) {
        blueslip.error("Trying to get menu items when schedule popover is closed.");
        return undefined;
    }

    return $send_later_options.find("[tabindex='0']");
}

function focus_first_send_later_popover_item(): void {
    // It is recommended to only call this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_send_later_menu_items();
    popover_menus.focus_first_popover_item($items);
}

export function toggle(): void {
    send_later_popover_keyboard_toggle = true;
    $("#send_later i").trigger("click");
}

export function initialize(): void {
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
                assert(send_at_timestamp !== undefined);
                do_schedule_message(send_at_timestamp);
                popover_menus.hide_current_popover_if_visible(instance);
            });
            // Handle clicks on Enter-to-send settings
            $popper.one("click", ".enter_sends_choice", (e) => {
                const selected_behaviour = $(e.currentTarget)
                    .find("input[type='radio']")
                    .attr("value");
                const selected_behaviour_bool = selected_behaviour === "true";
                user_settings.enter_sends = selected_behaviour_bool;

                channel.patch({
                    url: "/json/settings",
                    data: {enter_sends: selected_behaviour_bool},
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
                open_schedule_message_menu(undefined, util.the($("#send_later i")));
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
            popover_menus.popover_instances.send_later = null;
            send_later_popover_keyboard_toggle = false;
        },
    });
}

// This function is exported for unit testing purposes.
export function should_update_send_later_options(date: Date): boolean {
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

export function update_send_later_options(): void {
    const now = new Date();
    if (should_update_send_later_options(now)) {
        const filtered_send_opts = scheduled_messages.get_filtered_send_opts(now);
        const $new_send_later_options = $(render_schedule_message_popover(filtered_send_opts));
        $("#send-later-options").replaceWith($new_send_later_options);
        initialize_recurring_builder($new_send_later_options);
    }
}
