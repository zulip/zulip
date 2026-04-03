import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_channel_folder_setting_popover from "../templates/popovers/channel_folder_setting_popover.hbs";
import render_left_sidebar_folder_popover from "../templates/popovers/left_sidebar/left_sidebar_folder_popover.hbs";

import * as channel from "./channel.ts";
import * as channel_folders_ui from "./channel_folders_ui.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as pm_list from "./pm_list.ts";
import * as popover_menus from "./popover_menus.ts";
import * as settings_data from "./settings_data.ts";
import {current_user} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as ui_util from "./ui_util.ts";
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
                ui_util.parse_html(
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
                ui_util.parse_html(
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

    $("#streams_list").on(
        "click",
        ".stream-list-section-container .folder-section-sidebar-menu-icon",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();

            const folder_id = Number.parseInt(
                $(this).closest(".stream-list-section-container").attr("data-section-id")!,
                10,
            );
            popover_menus.toggle_popover_menu(this, {
                ...popover_menus.left_sidebar_tippy_options,
                theme: "popover-menu",
                onMount(instance) {
                    const $popper = $(instance.popper);
                    assert(instance.reference instanceof HTMLElement);
                    ui_util.show_left_sidebar_menu_icon(instance.reference);
                    $popper.one("click", "#folder_popover_view_channels", () => {
                        let section = "all";
                        if (current_user.is_guest) {
                            section = "subscribed";
                        }
                        stream_settings_ui.launch(section, undefined, undefined, folder_id);
                    });
                    $popper.one("click", "#folder_popover_manage_folder", () => {
                        channel_folders_ui.handle_editing_channel_folder(folder_id);
                    });
                },
                onShow(instance) {
                    instance.setContent(
                        ui_util.parse_html(
                            render_left_sidebar_folder_popover({
                                can_manage_folder: settings_data.can_user_manage_folder(),
                            }),
                        ),
                    );
                    popover_menus.on_show_prep(instance);

                    return undefined;
                },
                onHidden(instance) {
                    ui_util.hide_left_sidebar_menu_icon();
                    instance.destroy();
                },
            });
        },
    );
}
