/* Module for popovers that have been ported to the modern
   TippyJS/Popper popover library from the legacy Bootstrap
   popovers system in popovers.js. */

import $ from "jquery";
import {delegate} from "tippy.js";

import render_left_sidebar_stream_setting_popover from "../templates/left_sidebar_stream_setting_popover.hbs";
import render_mobile_message_buttons_popover_content from "../templates/mobile_message_buttons_popover_content.hbs";

import * as compose_actions from "./compose_actions";
import * as narrow_state from "./narrow_state";
import * as popovers from "./popovers";
import * as settings_data from "./settings_data";

let left_sidebar_stream_setting_popover_displayed = false;
let compose_mobile_button_popover_displayed = false;

const default_popover_props = {
    delay: 0,
    appendTo: () => document.body,
    trigger: "click",
    allowHTML: true,
    interactive: true,
    hideOnClick: true,
    /* The light-border TippyJS theme is a bit of a misnomer; it
       is a popover styling similar to Bootstrap.  We've also customized
       its CSS to support Zulip's night theme. */
    theme: "light-border",
    touch: true,
};

export function is_left_sidebar_stream_setting_popover_displayed() {
    return left_sidebar_stream_setting_popover_displayed;
}

export function is_compose_mobile_button_popover_displayed() {
    return compose_mobile_button_popover_displayed;
}

export function initialize() {
    delegate("body", {
        ...default_popover_props,
        target: "#streams_inline_cog",
        onShow(instance) {
            popovers.hide_all_except_sidebars(instance);
            instance.setContent(
                render_left_sidebar_stream_setting_popover({
                    can_create_streams: settings_data.user_can_create_streams(),
                }),
            );
            left_sidebar_stream_setting_popover_displayed = true;
            $(instance.popper).one("click", instance.hide);
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
            popovers.hide_all_except_sidebars(instance);
            instance.setContent(
                render_mobile_message_buttons_popover_content({
                    is_in_private_narrow: narrow_state.narrowed_to_pms(),
                }),
            );
            compose_mobile_button_popover_displayed = true;

            const $popper = $(instance.popper);
            $popper.one("click", instance.hide);
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
}
