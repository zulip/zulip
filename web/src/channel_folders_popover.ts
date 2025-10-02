import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_left_sidebar_channels_folder_setting_popover from "../templates/popovers/left_sidebar/left_sidebar_channels_folder_setting_popover.hbs";

import * as channel from "./channel.ts";
import * as popover_menus from "./popover_menus.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

function do_change_show_channel_folders(instance: tippy.Instance): void {
    const show_channel_folders = user_settings.web_left_sidebar_show_channel_folders;
    const data = {
        web_left_sidebar_show_channel_folders: JSON.stringify(!show_channel_folders),
    };
    void channel.patch({
        url: "/json/settings",
        data,
    });
    popover_menus.hide_current_popover_if_visible(instance);
}

export function initialize(): void {
    popover_menus.register_popover_menu("#left-sidebar-search .channel-folders-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        theme: "popover-menu",
        onMount(instance) {
            const $popper = $(instance.popper);
            assert(instance.reference instanceof HTMLElement);
            $popper.one("click", "#left_sidebar_channel_folders", () => {
                do_change_show_channel_folders(instance);
            });
        },
        onShow(instance) {
            const show_channel_folders = user_settings.web_left_sidebar_show_channel_folders;
            // Assuming that the instance can be shown, track and
            // prep the instance for showing
            popover_menus.popover_instances.show_channels_sidebar = instance;
            instance.setContent(
                parse_html(
                    render_left_sidebar_channels_folder_setting_popover({show_channel_folders}),
                ),
            );
            popover_menus.on_show_prep(instance);

            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.show_channels_sidebar = null;
        },
    });
}
