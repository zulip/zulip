import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_channel_folder_setting_popover from "../templates/popovers/channel_folder_setting_popover.hbs";

import * as channel from "./channel.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as pm_list from "./pm_list.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_list from "./stream_list.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

function do_change_show_channel_folders_left_sidebar(instance: tippy.Instance): void {
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

function do_change_show_channel_folders_inbox(instance: tippy.Instance): void {
    const show_channel_folders = user_settings.web_inbox_show_channel_folders;
    const data = {
        web_inbox_show_channel_folders: JSON.stringify(!show_channel_folders),
    };
    void channel.patch({
        url: "/json/settings",
        data,
    });
    popover_menus.hide_current_popover_if_visible(instance);
}

function expand_all_sections(instance: tippy.Instance): void {
    // Expand Views section
    left_sidebar_navigation_area.force_expand_views();

    // Expand Direct Messages section
    if (pm_list.is_private_messages_collapsed()) {
        pm_list.expand();
    }

    // Expand all channel/stream sections
    stream_list.expand_all_stream_sections();

    popover_menus.hide_current_popover_if_visible(instance);
}

function collapse_all_sections(instance: tippy.Instance): void {
    // Collapse Views section
    left_sidebar_navigation_area.force_collapse_views();

    // Collapse Direct Messages section
    if (!pm_list.is_private_messages_collapsed()) {
        pm_list.close();
    }

    // Collapse all channel/stream sections
    stream_list.collapse_all_stream_sections();
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
                do_change_show_channel_folders_left_sidebar(instance);
            });
            $popper.one("click", "#left_sidebar_expand_all", () => {
                expand_all_sections(instance);
            });
            $popper.one("click", "#left_sidebar_collapse_all", () => {
                collapse_all_sections(instance);
            });
        },
        onShow(instance) {
            const show_channel_folders = user_settings.web_left_sidebar_show_channel_folders;
            const show_collapse_expand_all_options = true;
            // Assuming that the instance can be shown, track and
            // prep the instance for showing
            popover_menus.popover_instances.show_folders_sidebar = instance;
            instance.setContent(
                parse_html(
                    render_channel_folder_setting_popover({
                        show_channel_folders,
                        channel_folders_id: "left_sidebar_channel_folders",
                        show_collapse_expand_all_options,
                    }),
                ),
            );
            popover_menus.on_show_prep(instance);

            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.show_folders_sidebar = null;
        },
    });

    popover_menus.register_popover_menu("#inbox-view .channel-folders-inbox-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        theme: "popover-menu",
        onMount(instance) {
            const $popper = $(instance.popper);
            assert(instance.reference instanceof HTMLElement);
            $popper.one("click", "#inbox_channel_folders", () => {
                do_change_show_channel_folders_inbox(instance);
            });
        },
        onShow(instance) {
            const show_channel_folders = user_settings.web_inbox_show_channel_folders;
            const show_collapse_expand_all_options = false;
            // Assuming that the instance can be shown, track and
            // prep the instance for showing
            popover_menus.popover_instances.show_folders_inbox = instance;
            instance.setContent(
                parse_html(
                    render_channel_folder_setting_popover({
                        show_channel_folders,
                        channel_folders_id: "inbox_channel_folders",
                        show_collapse_expand_all_options,
                    }),
                ),
            );
            popover_menus.on_show_prep(instance);

            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.show_folders_inbox = null;
        },
    });
}
