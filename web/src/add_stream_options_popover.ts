import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_left_sidebar_stream_setting_popover from "../templates/popovers/left_sidebar/left_sidebar_stream_setting_popover.hbs";

import * as popover_menus from "./popover_menus.ts";
import * as settings_data from "./settings_data.ts";
import {parse_html} from "./ui_util.ts";

export function initialize(): void {
    popover_menus.register_popover_menu(
        "#add_streams_button",
        {
            theme: "popover-menu",
            onMount(instance) {
                popover_menus.focus_popover(instance);
            },
            onShow(instance) {
                const can_create_streams =
                    settings_data.user_can_create_private_streams() ||
                    settings_data.user_can_create_public_streams() ||
                    settings_data.user_can_create_web_public_streams();

                if (!can_create_streams) {
                    // If the user can't create streams, we directly
                    // navigate them to the Stream settings subscribe UI.
                    window.location.assign("#channels/all");
                    // Returning false from an onShow handler cancels the show.
                    return false;
                }

                // Assuming that the instance can be shown, track and
                // prep the instance for showing
                popover_menus.popover_instances.stream_settings = instance;
                instance.setContent(parse_html(render_left_sidebar_stream_setting_popover()));
                popover_menus.on_show_prep(instance);

                //  When showing the popover menu, we want the
                // "Add channels" and the "Filter channels" tooltip
                //  to appear below the "Add channels" icon.
                const streams_inline_icon: tippy.ReferenceElement | undefined =
                    $("#streams_inline_icon").get(0);
                assert(streams_inline_icon !== undefined);
                streams_inline_icon._tippy?.setProps({
                    placement: "bottom",
                });

                return undefined;
            },
            onHidden(instance) {
                instance.destroy();
                popover_menus.popover_instances.stream_settings = null;

                //  After the popover menu is closed, we want the
                //  "Add channels" and the "Filter channels" tooltip
                //  to appear at it's original position that is
                //  above the "Add channels" icon.
                const streams_inline_icon: tippy.ReferenceElement | undefined =
                    $("#streams_inline_icon").get(0);
                assert(streams_inline_icon !== undefined);
                streams_inline_icon._tippy?.setProps({
                    placement: "top",
                });
            },
        },
        {also_trigger_on_enter: true},
    );
}
