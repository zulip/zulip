/* Module for popovers that have been ported to the modern
   TippyJS/Popper popover library from the legacy Bootstrap
   popovers system in popovers.js. */

import {add, format} from "date-fns";
import $ from "jquery";
import tippy, {delegate} from "tippy.js";

import render_compose_control_buttons_popover from "../templates/compose_control_buttons_popover.hbs";
import render_compose_select_enter_behaviour_popover from "../templates/compose_select_enter_behaviour_popover.hbs";
import render_left_sidebar_stream_setting_popover from "../templates/left_sidebar_stream_setting_popover.hbs";
import render_mobile_message_buttons_popover_content from "../templates/mobile_message_buttons_popover_content.hbs";
import render_send_later_popover from "../templates/send_later_popover.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as common from "./common";
import * as compose from "./compose";
import * as compose_actions from "./compose_actions";
import * as flatpickr from "./flatpickr";
import * as giphy from "./giphy";
import {$t, $t_html} from "./i18n";
import * as narrow_state from "./narrow_state";
import * as popovers from "./popovers";
import * as reminder from "./reminder";
import * as settings_data from "./settings_data";
import {parse_html} from "./ui_util";
import {user_settings} from "./user_settings";

let left_sidebar_stream_setting_popover_displayed = false;
let compose_mobile_button_popover_displayed = false;
export let compose_enter_sends_popover_displayed = false;
let compose_send_later_popover_displayed = false;
let compose_control_buttons_popover_instance;
let selected_send_later_time;
let selected_send_later_id;

export function is_time_selected_for_schedule() {
    return selected_send_later_id !== undefined;
}

export function reset_selected_schedule_time() {
    selected_send_later_id = undefined;
}

export function get_compose_control_buttons_popover() {
    return compose_control_buttons_popover_instance;
}

const default_popover_props = {
    delay: 0,
    appendTo: () => document.body,
    trigger: "click",
    interactive: true,
    hideOnClick: true,
    /* The light-border TippyJS theme is a bit of a misnomer; it
       is a popover styling similar to Bootstrap.  We've also customized
       its CSS to support Zulip's dark theme. */
    theme: "light-border",
    touch: true,
};

export function any_active() {
    return (
        left_sidebar_stream_setting_popover_displayed ||
        compose_mobile_button_popover_displayed ||
        compose_control_buttons_popover_instance ||
        compose_enter_sends_popover_displayed ||
        compose_send_later_popover_displayed
    );
}

function on_show_prep(instance) {
    $(instance.popper).one("click", instance.hide);
    popovers.hide_all_except_sidebars(instance);
}

const send_later_hours = {
    in_one_hour: {
        text: $t({defaultMessage: "1 hour"}),
        hours: 1,
    },
    in_two_hours: {
        text: $t({defaultMessage: "2 hours"}),
        hours: 2,
    },
    in_four_hours: {
        text: $t({defaultMessage: "4 hours"}),
        hours: 4,
    },
};

const send_later_tomorrow = {
    tomorrow_nine_am: {
        text: $t({defaultMessage: "Tomorrow 9:00 AM"}),
        time: "9:00 am",
    },
    tomorrow_two_pm: {
        text: $t({defaultMessage: "Tomorrow 2:00 PM "}),
        time: "2:00 pm",
    },
};

const send_later_days_and_weeks = {
    in_one_day: {
        text: $t({defaultMessage: "1 day"}),
        days: 1,
    },
    in_two_days: {
        text: $t({defaultMessage: "2 days"}),
        days: 2,
    },
    in_one_week: {
        text: $t({defaultMessage: "1 week"}),
        days: 7,
    },
    in_two_weeks: {
        text: $t({defaultMessage: "2 weeks"}),
        days: 14,
    },
    in_one_month: {
        text: $t({defaultMessage: "1 month"}),
        days: 30,
    },
};

const send_later_custom = {
    text: $t({defaultMessage: "Custom"}),
};

function reset_compose_scheduling_state_on_success() {
    $("#compose-textarea").prop("disabled", false);
    $("#schedule-confirm").hide();
    $("#schedule-confirm")[0]._tippy.destroy();
    reset_selected_schedule_time();
    $("#compose-send-button").show();
    compose.clear_compose_box();
}

export function schedule_message_to_custom_date() {
    const request = compose.create_message_object();
    request.content = `/schedule ${selected_send_later_time}\n` + request.content;
    reminder.schedule_message(request, reset_compose_scheduling_state_on_success);
}

export function initialize() {
    delegate("body", {
        ...default_popover_props,
        target: "#streams_inline_icon",
        onShow(instance) {
            const can_create_streams =
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams();
            on_show_prep(instance);

            if (!can_create_streams) {
                // If the user can't create streams, we directly
                // navigate them to the Manage streams subscribe UI.
                window.location.assign("#streams/all");
                // Returning false from an onShow handler cancels the show.
                return false;
            }

            instance.setContent(parse_html(render_left_sidebar_stream_setting_popover()));
            left_sidebar_stream_setting_popover_displayed = true;
            return true;
        },
        onHidden() {
            left_sidebar_stream_setting_popover_displayed = false;
        },
    });

    // compose box buttons popover shown on mobile widths.
    delegate("body", {
        ...default_popover_props,
        target: ".compose_mobile_button",
        placement: "top",
        onShow(instance) {
            on_show_prep(instance);
            instance.setContent(
                parse_html(
                    render_mobile_message_buttons_popover_content({
                        is_in_private_narrow: narrow_state.narrowed_to_pms(),
                    }),
                ),
            );
            compose_mobile_button_popover_displayed = true;

            const $popper = $(instance.popper);
            $popper.one("click", ".compose_mobile_stream_button", () => {
                compose_actions.start("stream", {trigger: "new topic button"});
            });
            $popper.one("click", ".compose_mobile_private_button", () => {
                compose_actions.start("private");
            });
        },
        onHidden(instance) {
            // Destroy instance so that event handlers
            // are destroyed too.
            instance.destroy();
            compose_mobile_button_popover_displayed = false;
        },
    });

    // We need to hide instance manually for popover due to
    // `$("body").on("click"...` method not being triggered for
    // the elements when we do:
    // `$(instance.popper).one("click", instance.hide); in onShow.
    // Cannot reproduce it on codepen -
    // https://codepen.io/amanagr/pen/jOLoKVg
    // So, probably a bug on our side.
    delegate("body", {
        ...default_popover_props,
        target: ".compose_control_menu_wrapper",
        placement: "top",
        onShow(instance) {
            instance.setContent(
                parse_html(
                    render_compose_control_buttons_popover({
                        giphy_enabled: giphy.is_giphy_enabled(),
                    }),
                ),
            );
            compose_control_buttons_popover_instance = instance;
            popovers.hide_all_except_sidebars(instance);
        },
        onHidden() {
            compose_control_buttons_popover_instance = undefined;
        },
    });

    delegate("body", {
        ...default_popover_props,
        target: ".enter_sends",
        placement: "top",
        onShow(instance) {
            on_show_prep(instance);
            instance.setContent(
                parse_html(
                    render_compose_select_enter_behaviour_popover({
                        enter_sends_true: user_settings.enter_sends,
                    }),
                ),
            );
            compose_enter_sends_popover_displayed = true;
        },
        onMount(instance) {
            common.adjust_mac_shortcuts(".enter_sends_choices kbd");

            $(instance.popper).one("click", ".enter_sends_choice", (e) => {
                let selected_behaviour = $(e.currentTarget)
                    .find("input[type='radio']")
                    .attr("value");
                selected_behaviour = selected_behaviour === "true"; // Convert to bool
                user_settings.enter_sends = selected_behaviour;
                $(`.enter_sends_${!selected_behaviour}`).hide();
                $(`.enter_sends_${selected_behaviour}`).show();

                // Refocus in the content box so you can continue typing or
                // press Enter to send.
                $("#compose-textarea").trigger("focus");

                return channel.patch({
                    url: "/json/settings",
                    data: {enter_sends: selected_behaviour},
                });
            });
        },
        onHidden(instance) {
            instance.destroy();
            compose_enter_sends_popover_displayed = false;
        },
    });

    $("body").on("click", "#schedule-confirm", (e) => {
        schedule_message_to_custom_date();

        e.preventDefault();
        e.stopPropagation();
    });

    function show_schedule_confirm_button(send_at_time, not_from_flatpickr) {
        if (!send_at_time) {
            return;
        }
        if (!not_from_flatpickr) {
            selected_send_later_id = "send-later-custom-input";
            send_at_time = format(new Date(send_at_time), "MMM d yyyy h:mm a");
        }

        selected_send_later_time = send_at_time;

        $("#schedule-confirm").show();
        tippy("#schedule-confirm", {
            content: $t_html({defaultMessage: `Send at {send_at_time}`}, {send_at_time}),
        });

        $("#compose-send-button").hide();
    }

    function set_compose_box_schedule(element) {
        const send_later_in = element.id;
        selected_send_later_id = send_later_in;
        const send_later_class = element.classList[0];
        switch (send_later_class) {
            case "send_later_hours": {
                const send_at_time = format(
                    add(new Date(), {minutes: send_later_hours[send_later_in].hours * 60}),
                    "MMM d yyyy h:mm a",
                );
                return send_at_time;
            }
            case "send_later_tomorrow": {
                const send_time = send_later_tomorrow[send_later_in].time;
                const date = new Date();
                const scheduled_date = date.setDate(date.getDate() + 1);
                const send_at_time = format(scheduled_date, "MMM d yyyy ") + send_time;
                return send_at_time;
            }
            case "send_later_days_and_weeks": {
                const send_at_time = format(
                    add(new Date(), {days: send_later_days_and_weeks[send_later_in].days}),
                    "MMM d yyyy h:mm a",
                );
                return send_at_time;
            }
            // No default
        }
        blueslip.error("Not a valid time.");
        return false;
    }

    function reset_send_later_popover_state() {
        selected_send_later_id = undefined;
        selected_send_later_time = undefined;
        $("#schedule-confirm").hide();
        $("#compose-send-button").show();
    }

    delegate("body", {
        ...default_popover_props,
        target: "#send_later i",
        onShow(instance) {
            popovers.hide_all_except_sidebars(instance);
            instance.setContent(
                parse_html(render_send_later_popover({
                    send_later_hours,
                    send_later_tomorrow,
                    send_later_days_and_weeks,
                    send_later_custom,
                })),
            );

            compose_send_later_popover_displayed = true;
            $(instance.popper).one("click", instance.hide);
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.one("click", "#send-later-custom-input", (e) => {
                if ($(e.target).hasClass("selected")) {
                    reset_send_later_popover_state();
                    return;
                }
                flatpickr.show_flatpickr(
                    $("#send_later")[0],
                    show_schedule_confirm_button,
                    new Date(),
                );
            });

            $popper.one(
                "click",
                ".send_later_hours, .send_later_tomorrow, .send_later_days_and_weeks",
                (e) => {
                    if ($(e.target).hasClass("selected")) {
                        reset_send_later_popover_state();
                        return;
                    }
                    const send_at_time = set_compose_box_schedule(e.currentTarget);
                    const not_from_flatpickr = true;
                    show_schedule_confirm_button(send_at_time, not_from_flatpickr);

                    instance.hide();
                    e.stopPropagation();
                    e.preventDefault();
                },
            );
            $("#" + selected_send_later_id).addClass("selected");
        },
        onHidden(instance) {
            instance.destroy();
            compose_send_later_popover_displayed = false;
        },
    });
}
