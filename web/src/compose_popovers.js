import $ from "jquery";
import {delegate} from "tippy.js";

import render_compose_control_buttons_popover from "../templates/popovers/compose_control_buttons/compose_control_buttons_popover.hbs";
import render_mobile_message_buttons_popover from "../templates/popovers/mobile_message_buttons_popover.hbs";

import * as compose_actions from "./compose_actions";
import * as giphy from "./giphy";
import * as narrow_state from "./narrow_state";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as rows from "./rows";
import {parse_html} from "./ui_util";

export function initialize() {
    // compose box buttons popover shown on mobile widths.
    // We want this click event to propagate and hide other popovers
    // that could possibly obstruct user from using this popover.
    delegate("body", {
        ...popover_menus.default_popover_props,
        // Attach the click event to `.mobile_button_container`, since
        // the button (`.compose_mobile_button`) already has a hover
        // action attached, for showing the keyboard shortcut,
        // and Tippy cannot handle events that trigger two different
        // actions
        target: ".mobile_button_container",
        placement: "top",
        onShow(instance) {
            popover_menus.popover_instances.compose_mobile_button = instance;
            popover_menus.on_show_prep(instance);
            instance.setContent(
                parse_html(
                    render_mobile_message_buttons_popover({
                        is_in_private_narrow: narrow_state.narrowed_to_pms(),
                    }),
                ),
            );
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.one("click", ".compose_mobile_stream_button", (e) => {
                compose_actions.start({
                    mesage_type: "stream",
                    trigger: "clear topic button",
                });
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });
            $popper.one("click", ".compose_mobile_direct_message_button", (e) => {
                compose_actions.start({
                    message_type: "private",
                });
                e.stopPropagation();
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            // Destroy instance so that event handlers
            // are destroyed too.
            instance.destroy();
            popover_menus.popover_instances.compose_mobile_button = undefined;
        },
    });

    // Click event handlers for it are handled in `compose_ui` and
    // we don't want to close this popover on click inside it but
    // only if user clicked outside it.
    popover_menus.register_popover_menu(".compose_control_menu_wrapper", {
        placement: "top",
        onShow(instance) {
            const parent_row = rows.get_closest_row(instance.reference);
            let preview_mode_on;
            // If the popover is opened from a message edit form, we want to
            // infer the preview mode from that row, else from the compose box.
            if (parent_row.length) {
                preview_mode_on = parent_row.hasClass("preview_mode");
            } else {
                preview_mode_on = $("#compose").hasClass("preview_mode");
            }
            instance.setContent(
                parse_html(
                    render_compose_control_buttons_popover({
                        giphy_enabled: giphy.is_giphy_enabled(),
                        preview_mode_on,
                        inside_popover: true,
                    }),
                ),
            );
            popover_menus.popover_instances.compose_control_buttons = instance;
            popovers.hide_all();
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.compose_control_buttons = undefined;
        },
    });
}
