import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_left_sidebar_stream_setting_popover from "../templates/popovers/left_sidebar/left_sidebar_stream_setting_popover.hbs";

import * as popover_menus from "./popover_menus.ts";
import * as settings_data from "./settings_data.ts";
import {parse_html} from "./ui_util.ts";

export function initialize(): void {
    popover_menus.register_popover_menu("#streams_inline_icon", {
        theme: "popover-menu",
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

            $("#streams_header").addClass("showing-streams-popover");

            //  When showing the popover menu, we want the
            // "Add channels" and the "Filter channels" tooltip
            //  to appear below the "Add channels" icon.
            const add_streams_tooltip: tippy.ReferenceElement | undefined =
                $("#add_streams_tooltip").get(0);
            assert(add_streams_tooltip !== undefined);
            add_streams_tooltip._tippy?.setProps({
                placement: "bottom",
            });

            const filter_streams_tooltip: (tippy.ReferenceElement & HTMLElement) | undefined =
                $("#filter_streams_tooltip").get(0);
            // If `filter_streams_tooltip` is not triggered yet, this will set its initial placement.
            assert(filter_streams_tooltip !== undefined);
            filter_streams_tooltip.dataset.tippyPlacement = "bottom";
            filter_streams_tooltip._tippy?.setProps({
                placement: "bottom",
            });

            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.stream_settings = null;

            $("#streams_header").removeClass("showing-streams-popover");

            //  After the popover menu is closed, we want the
            //  "Add channels" and the "Filter channels" tooltip
            //  to appear at it's original position that is
            //  above the "Add channels" icon.
            const add_streams_tooltip: tippy.ReferenceElement | undefined =
                $("#add_streams_tooltip").get(0);
            assert(add_streams_tooltip !== undefined);
            add_streams_tooltip._tippy?.setProps({
                placement: "top",
            });

            const filter_streams_tooltip: (tippy.ReferenceElement & HTMLElement) | undefined =
                $("#filter_streams_tooltip").get(0);
            assert(filter_streams_tooltip !== undefined);
            filter_streams_tooltip.dataset.tippyPlacement = "top";
            filter_streams_tooltip._tippy?.setProps({
                placement: "top",
            });
        },
    });
}
