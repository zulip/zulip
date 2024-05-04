import $ from "jquery";
import {delegate} from "tippy.js";

import render_send_later_popover from "../templates/popovers/send_later_popover.hbs";
import render_send_later_modal from "../templates/send_later_modal.hbs";
import render_send_later_modal_options from "../templates/send_later_modal_options.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as common from "./common";
import * as compose from "./compose";
import * as compose_state from "./compose_state";
import * as compose_validate from "./compose_validate";
import * as drafts from "./drafts";
import * as flatpickr from "./flatpickr";
import * as modals from "./modals";
import * as popover_menus from "./popover_menus";
import * as scheduled_messages from "./scheduled_messages";
import {parse_html} from "./ui_util";
import {user_settings} from "./user_settings";

export const SCHEDULING_MODAL_UPDATE_INTERVAL_IN_MILLISECONDS = 60 * 1000;
const ENTER_SENDS_SELECTION_DELAY = 600;

let send_later_popover_keyboard_toggle = false;

function set_compose_box_schedule(element) {
    const selected_send_at_time = element.dataset.sendStamp / 1000;
    return selected_send_at_time;
}

export function open_send_later_menu() {
    if (!compose_validate.validate(true)) {
        return;
    }

    // Only show send later options that are possible today.
    const date = new Date();
    const filtered_send_opts = scheduled_messages.get_filtered_send_opts(date);
    $("body").append($(render_send_later_modal(filtered_send_opts)));
    let interval;

    modals.open("send_later_modal", {
        autoremove: true,
        on_show() {
            interval = setInterval(
                update_send_later_options,
                SCHEDULING_MODAL_UPDATE_INTERVAL_IN_MILLISECONDS,
            );

            const $send_later_modal = $("#send_later_modal");

            // Upon the first keydown event, we focus on the first element in the list,
            // enabling keyboard navigation that is handled by `hotkey.js` and `list_util.ts`.
            $send_later_modal.one("keydown", () => {
                const $options = $send_later_modal.find("a");
                $options[0].focus();

                $send_later_modal.on("keydown", (e) => {
                    if (e.key === "Enter") {
                        e.target.click();
                    }
                });
            });

            $send_later_modal.on("click", ".send_later_custom", (e) => {
                const $send_later_modal_content = $send_later_modal.find(".modal__content");
                const current_time = new Date();
                flatpickr.show_flatpickr(
                    $(".send_later_custom")[0],
                    do_schedule_message,
                    new Date(current_time.getTime() + 60 * 60 * 1000),
                    {
                        minDate: new Date(
                            current_time.getTime() +
                                scheduled_messages.MINIMUM_SCHEDULED_MESSAGE_DELAY_SECONDS * 1000,
                        ),
                        onClose() {
                            // Return to normal state.
                            $send_later_modal_content.css("pointer-events", "all");
                        },
                    },
                );
                // Disable interaction with rest of the options in the modal.
                $send_later_modal_content.css("pointer-events", "none");
                e.preventDefault();
                e.stopPropagation();
            });
            $send_later_modal.one(
                "click",
                ".send_later_today, .send_later_tomorrow, .send_later_monday",
                (e) => {
                    const send_at_time = set_compose_box_schedule(e.currentTarget);
                    do_schedule_message(send_at_time);
                    e.preventDefault();
                    e.stopPropagation();
                },
            );
        },
        on_shown() {
            // When shown, we should give the modal focus to correctly handle keyboard events.
            const $send_later_modal_overlay = $("#send_later_modal .modal__overlay");
            $send_later_modal_overlay.trigger("focus");
        },
        on_hide() {
            clearInterval(interval);
        },
    });
}

export function do_schedule_message(send_at_time) {
    modals.close_if_open("send_later_modal");

    if (!Number.isInteger(send_at_time)) {
        // Convert to timestamp if this is not a timestamp.
        send_at_time = Math.floor(Date.parse(send_at_time) / 1000);
    }
    scheduled_messages.set_selected_schedule_timestamp(send_at_time);
    compose.finish(true);
}

function get_send_later_menu_items() {
    const $current_schedule_popover_elem = $("[data-tippy-root] #send_later_popover");
    if (!$current_schedule_popover_elem) {
        blueslip.error("Trying to get menu items when schedule popover is closed.");
        return undefined;
    }

    return $current_schedule_popover_elem.find("li:not(.divider):visible a");
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
    delegate("body", {
        ...popover_menus.default_popover_props,
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
            common.adjust_mac_kbd_tags(".enter_sends_choices kbd");
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
                $(`.enter_sends_${!selected_behaviour}`).hide();
                $(`.enter_sends_${selected_behaviour}`).show();

                // Refocus in the content box so you can continue typing or
                // press Enter to send.
                $("textarea#compose-textarea").trigger("focus");

                channel.patch({
                    url: "/json/settings",
                    data: {enter_sends: selected_behaviour},
                });
                e.stopPropagation();
                setTimeout(() => {
                    popover_menus.hide_current_popover_if_visible(instance);
                }, ENTER_SENDS_SELECTION_DELAY);
            });
            // Handle Send later clicks
            $popper.one("click", ".open_send_later_modal", () => {
                open_send_later_menu();
                popover_menus.hide_current_popover_if_visible(instance);
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
        $("#send_later_options").replaceWith(
            $(render_send_later_modal_options(filtered_send_opts)),
        );
    }
}
