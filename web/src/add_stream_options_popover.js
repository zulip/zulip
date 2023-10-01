import $ from "jquery";

import render_left_sidebar_stream_setting_popover from "../templates/left_sidebar_stream_setting_popover.hbs";

import * as popover_menus from "./popover_menus";
import * as settings_data from "./settings_data";
import {parse_html} from "./ui_util";

export function initialize() {
    popover_menus.register_popover_menu("#streams_inline_icon", {
        onShow(instance) {
            const can_create_streams =
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams();

            if (!can_create_streams) {
                // If the user can't create streams, we directly
                // navigate them to the Manage streams subscribe UI.
                window.location.assign("#streams/all");
                // Returning false from an onShow handler cancels the show.
                return false;
            }

            // Assuming that the instance can be shown, track and
            // prep the instance for showing
            popover_menus.popover_instances.stream_settings = instance;
            instance.setContent(parse_html(render_left_sidebar_stream_setting_popover()));
            popover_menus.on_show_prep(instance);

            //  When showing the popover menu, we want the
            // "Add streams" and the "Filter streams" tooltip
            //  to appear below the "Add streams" icon.
            const add_streams_tooltip = $("#add_streams_tooltip").get(0);
            add_streams_tooltip._tippy?.setProps({
                placement: "bottom",
            });
            const filter_streams_tooltip = $("#filter_streams_tooltip").get(0);
            // If `filter_streams_tooltip` is not triggered yet, this will set its initial placement.
            filter_streams_tooltip.dataset.tippyPlacement = "bottom";
            filter_streams_tooltip._tippy?.setProps({
                placement: "bottom",
            });

            // The linter complains about unbalanced returns
            return true;
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.stream_settings = undefined;
            //  After the popover menu is closed, we want the
            //  "Add streams" and the "Filter streams" tooltip
            //  to appear at it's original position that is
            //  above the "Add streams" icon.
            const add_streams_tooltip = $("#add_streams_tooltip").get(0);
            add_streams_tooltip._tippy?.setProps({
                placement: "top",
            });
            const filter_streams_tooltip = $("#filter_streams_tooltip").get(0);
            filter_streams_tooltip.dataset.tippyPlacement = "top";
            filter_streams_tooltip._tippy?.setProps({
                placement: "top",
            });
        },
    });
}
