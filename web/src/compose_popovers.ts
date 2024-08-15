import $ from "jquery";
import assert from "minimalistic-assert";

import render_compose_control_buttons_popover from "../templates/popovers/compose_control_buttons/compose_control_buttons_popover.hbs";

import * as giphy_state from "./giphy_state";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as rows from "./rows";
import {parse_html} from "./ui_util";

export function initialize(): void {
    // Click event handlers for it are handled in `compose_ui` and
    // we don't want to close this popover on click inside it but
    // only if user clicked outside it.
    popover_menus.register_popover_menu(".compose_control_menu_wrapper", {
        placement: "top",
        onShow(instance) {
            assert(instance.reference instanceof HTMLElement);
            const parent_row = rows.get_closest_row($(instance.reference));
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
                        giphy_enabled: giphy_state.is_giphy_enabled(),
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
            popover_menus.popover_instances.compose_control_buttons = null;
        },
    });
}
