import $ from "jquery";

import render_user_group_settings_deactivated_group_popover from "../templates/popovers/user_group_settings_deactivated_group_popover.hbs";

import * as popover_menus from "./popover_menus.ts";
import * as settings_data from "./settings_data.ts";
import {parse_html} from "./ui_util.ts";

export function initialize(): void {
    popover_menus.register_popover_menu("#more_options_user_group", {
        theme: "popover-menu",
        onShow(instance) {
            const parsedContent = parse_html(
                render_user_group_settings_deactivated_group_popover({
                    show_deactivated_user_groups: settings_data.show_deactivated_user_groups()
                }),
            );

            instance.setContent(parsedContent);

            popover_menus.on_show_prep(instance);
            return undefined;
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.on("click", "#user-group-settings-deactivated-groups-label-container", (e) => {
                e.preventDefault();
                settings_data.toggle_deactivated_group_visibility();
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            instance.destroy();
        },
    });
}