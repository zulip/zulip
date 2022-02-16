/* Module for popovers that have been ported to the modern
   TippyJS/Popper popover library from the legacy Bootstrap
   popovers system in popovers.js. */

import $ from "jquery";
import {delegate} from "tippy.js";

import render_compose_control_buttons_popover from "../templates/compose_control_buttons_popover.hbs";
import render_compose_select_enter_behaviour_popover from "../templates/compose_select_enter_behaviour_popover.hbs";
import render_left_sidebar_stream_setting_popover from "../templates/left_sidebar_stream_setting_popover.hbs";
import render_mobile_message_buttons_popover_content from "../templates/mobile_message_buttons_popover_content.hbs";

import * as channel from "./channel";
import * as common from "./common";
import * as compose_actions from "./compose_actions";
import * as giphy from "./giphy";
import * as narrow_state from "./narrow_state";
import * as popovers from "./popovers";
import * as settings_data from "./settings_data";
import {user_settings} from "./user_settings";

let left_sidebar_stream_setting_popover_displayed = false;
let compose_mobile_button_popover_displayed = false;
export let compose_enter_sends_popover_displayed = false;
let compose_control_buttons_popover_instance;

export function get_compose_control_buttons_popover() {
    return compose_control_buttons_popover_instance;
}

const default_popover_props = {
    delay: 0,
    appendTo: () => document.body,
    trigger: "click",
    allowHTML: true,
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
        compose_enter_sends_popover_displayed
    );
}

function on_show_prep(instance) {
    $(instance.popper).one("click", instance.hide);
    popovers.hide_all_except_sidebars(instance);
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

            instance.setContent(render_left_sidebar_stream_setting_popover());
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
                render_mobile_message_buttons_popover_content({
                    is_in_private_narrow: narrow_state.narrowed_to_pms(),
                }),
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
                render_compose_control_buttons_popover({
                    giphy_enabled: giphy.is_giphy_enabled(),
                }),
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
                render_compose_select_enter_behaviour_popover({
                    enter_sends_true: user_settings.enter_sends,
                }),
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
                    idempotent: true,
                    data: {enter_sends: selected_behaviour},
                });
            });
        },
        onHidden(instance) {
            instance.destroy();
            compose_enter_sends_popover_displayed = false;
        },
    });
}
