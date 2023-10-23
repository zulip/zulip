import $ from "jquery";

import render_drafts_sidebar_actions from "../templates/drafts_sidebar_action.hbs";
import render_left_sidebar_condensed_views_popover from "../templates/popovers/left_sidebar_condensed_views_popover.hbs";
import render_left_sidebar_inbox_popover from "../templates/popovers/left_sidebar_inbox_popover.hbs";
import render_starred_messages_sidebar_actions from "../templates/starred_messages_sidebar_actions.hbs";

import * as channel from "./channel";
import * as drafts from "./drafts";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as scheduled_messages from "./scheduled_messages";
import * as settings_config from "./settings_config";
import * as starred_messages from "./starred_messages";
import * as starred_messages_ui from "./starred_messages_ui";
import {parse_html, update_unread_count_in_dom} from "./ui_util";
import * as unread_ops from "./unread_ops";
import {user_settings} from "./user_settings";

function common_click_handlers() {
    $("body").on("click", ".set-default-view", (e) => {
        e.preventDefault();
        e.preventDefault();

        const default_view = $(e.currentTarget).attr("data-view-code");
        const data = {default_view};
        channel.patch({
            url: "/json/settings",
            data,
        });

        popovers.hide_all();
    });
}

export function initialize() {
    // Starred messages popover
    popover_menus.register_popover_menu(".starred-messages-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.starred_messages = instance;

            $popper.one("click", "#unstar_all_messages", () => {
                starred_messages_ui.confirm_unstar_all_messages();
                instance.hide();
            });
            $popper.one("click", "#toggle_display_starred_msg_count", () => {
                const data = {};
                const starred_msg_counts = user_settings.starred_message_counts;
                data.starred_message_counts = JSON.stringify(!starred_msg_counts);

                channel.patch({
                    url: "/json/settings",
                    data,
                });
                instance.hide();
            });
        },
        onShow(instance) {
            popovers.hide_all();
            const show_unstar_all_button = starred_messages.get_count() > 0;

            instance.setContent(
                parse_html(
                    render_starred_messages_sidebar_actions({
                        show_unstar_all_button,
                        starred_message_counts: user_settings.starred_message_counts,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.starred_messages = undefined;
        },
    });

    // Drafts popover
    popover_menus.register_popover_menu(".drafts-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.addClass("drafts-popover");
            popover_menus.popover_instances.drafts = instance;

            $popper.one("click", "#delete_all_drafts_sidebar", () => {
                drafts.confirm_delete_all_drafts();
                instance.hide();
            });
        },
        onShow(instance) {
            popovers.hide_all();

            instance.setContent(parse_html(render_drafts_sidebar_actions({})));
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.drafts = undefined;
        },
    });

    // Inbox popover
    popover_menus.register_popover_menu(".inbox-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.left_sidebar_inbox_popover = instance;

            $popper.one("click", "#mark_all_messages_as_read", () => {
                unread_ops.confirm_mark_all_as_read();
                instance.hide();
            });
        },
        onShow(instance) {
            popovers.hide_all();
            const view_code = settings_config.default_view_values.inbox.code;
            instance.setContent(
                parse_html(
                    render_left_sidebar_inbox_popover({
                        is_default_view: user_settings.default_view === view_code,
                        view_code,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_inbox_popover = undefined;
        },
    });

    popover_menus.register_popover_menu(".left-sidebar-navigation-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onShow(instance) {
            // Determine at show time whether there are scheduled messages,
            // so that Tippy properly calculates the height of the popover
            const scheduled_message_count = scheduled_messages.get_count();
            let has_scheduled_messages = false;
            if (scheduled_message_count > 0) {
                has_scheduled_messages = true;
            }
            popovers.hide_all();
            instance.setContent(
                parse_html(render_left_sidebar_condensed_views_popover({has_scheduled_messages})),
            );
        },
        onMount() {
            update_unread_count_in_dom(
                $(".condensed-views-popover-menu-drafts"),
                drafts.draft_model.getDraftCount(),
            );
            update_unread_count_in_dom(
                $(".condensed-views-popover-menu-scheduled-messages"),
                scheduled_messages.get_count(),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.top_left_sidebar = undefined;
        },
    });

    common_click_handlers();
}
