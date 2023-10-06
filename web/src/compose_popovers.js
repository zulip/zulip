import $ from "jquery";
import {delegate} from "tippy.js";

import render_compose_control_buttons_popover from "../templates/popovers/compose_control_buttons/compose_control_buttons_popover.hbs";
import render_compose_select_enter_behaviour_popover from "../templates/popovers/compose_select_enter_behaviour_popover.hbs";
import render_mobile_message_buttons_popover from "../templates/popovers/mobile_message_buttons_popover.hbs";

import * as channel from "./channel";
import * as common from "./common";
import * as compose_actions from "./compose_actions";
import * as giphy from "./giphy";
import * as narrow_state from "./narrow_state";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as rows from "./rows";
import {parse_html} from "./ui_util";
import {user_settings} from "./user_settings";

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
                compose_actions.start("stream", {trigger: "new topic button"});
                e.stopPropagation();
                instance.hide();
            });
            $popper.one("click", ".compose_mobile_private_button", (e) => {
                compose_actions.start("private");
                e.stopPropagation();
                instance.hide();
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

    popover_menus.register_popover_menu(".open_enter_sends_dialog", {
        placement: "top",
        onShow(instance) {
            popover_menus.on_show_prep(instance);
            instance.setContent(
                parse_html(
                    render_compose_select_enter_behaviour_popover({
                        enter_sends_true: user_settings.enter_sends,
                    }),
                ),
            );
        },
        onMount(instance) {
            popover_menus.popover_instances.compose_enter_sends = instance;
            common.adjust_mac_kbd_tags(".enter_sends_choices kbd");

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

                channel.patch({
                    url: "/json/settings",
                    data: {enter_sends: selected_behaviour},
                });
                e.stopPropagation();
                instance.hide();
            });
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.compose_enter_sends = undefined;
        },
    });
}
