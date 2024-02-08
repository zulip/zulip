import $ from "jquery";

import render_navbar_help_menu from "../templates/navbar_help_menu.hbs";

import {page_params} from "./page_params";
import * as popover_menus from "./popover_menus";
import {parse_html} from "./ui_util";

export function initialize(): void {
    popover_menus.register_popover_menu("#help-menu", {
        theme: "popover-menu",
        placement: "bottom",
        offset: [-50, 0],
        // The strategy: "fixed"; and eventlisteners modifier option
        // ensure that the personal menu does not modify its position
        // or disappear when user zooms the page.
        popperOptions: {
            strategy: "fixed",
            modifiers: [
                {
                    name: "eventListeners",
                    options: {
                        scroll: false,
                    },
                },
            ],
        },
        onMount(instance) {
            popover_menus.popover_instances.help_menu = instance;
        },
        onShow(instance) {
            instance.setContent(
                parse_html(
                    render_navbar_help_menu({
                        corporate_enabled: page_params.corporate_enabled,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.help_menu = null;
        },
    });
}

export function toggle(): void {
    // NOTE: Since to open help menu, you need to click on help navbar icon (which calls
    // tippyjs.hideAll()), or go via gear menu if using hotkeys, we don't need to
    // call tippyjs.hideAll() for it.
    $("#help-menu").trigger("click");
}
