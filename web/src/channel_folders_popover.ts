import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_left_sidebar_channels_folder_setting_popover from "../templates/popovers/left_sidebar/left_sidebar_channels_folder_setting_popover.hbs";

import * as channel from "./channel.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as pm_list from "./pm_list.ts";
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

function expand_all_sections(instance: tippy.Instance): void {
    // Expand Views section
    const $views_label_container = $("#views-label-container");
    const $views_label_icon = $("#toggle-top-left-navigation-area-icon");
    if ($views_label_container.hasClass("showing-condensed-navigation")) {
        left_sidebar_navigation_area.expand_views($views_label_container, $views_label_icon);
    }

    // Expand Direct Messages section
    if (pm_list.is_private_messages_collapsed()) {
        pm_list.expand();
    }

    // Expand all channel/stream sections
    $(".stream-list-section-container.collapsed").each(function () {
        const $container = $(this);
        $container.removeClass("collapsed");
        $container
            .find(".stream-list-section-toggle")
            .removeClass("rotate-icon-right")
            .addClass("rotate-icon-down");
    });

    popover_menus.hide_current_popover_if_visible(instance);
}

function collapse_all_sections(instance: tippy.Instance): void {
    // Collapse Views section
    const $views_label_container = $("#views-label-container");
    const $views_label_icon = $("#toggle-top-left-navigation-area-icon");
    if ($views_label_container.hasClass("showing-expanded-navigation")) {
        $views_label_container.addClass("showing-condensed-navigation");
        $views_label_container.removeClass("showing-expanded-navigation");
        $views_label_icon.addClass("rotate-icon-right");
        $views_label_icon.removeClass("rotate-icon-down");
    }

    // Collapse Direct Messages section
    if (!pm_list.is_private_messages_collapsed()) {
        pm_list.close();
    }

    // Collapse all channel/stream sections
    $(".stream-list-section-container:not(.collapsed)").each(function () {
        const $container = $(this);
        $container.addClass("collapsed");
        $container
            .find(".stream-list-section-toggle")
            .removeClass("rotate-icon-down")
            .addClass("rotate-icon-right");
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
            $popper.one("click", "#left_sidebar_expand_all", () => {
                expand_all_sections(instance);
            });
            $popper.one("click", "#left_sidebar_collapse_all", () => {
                collapse_all_sections(instance);
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
