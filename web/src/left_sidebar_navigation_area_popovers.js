import $ from "jquery";

import render_drafts_sidebar_actions from "../templates/drafts_sidebar_action.hbs";
import render_left_sidebar_all_messages_popover from "../templates/popovers/left_sidebar_all_messages_popover.hbs";
import render_left_sidebar_condensed_views_popover from "../templates/popovers/left_sidebar_condensed_views_popover.hbs";
import render_left_sidebar_inbox_popover from "../templates/popovers/left_sidebar_inbox_popover.hbs";
import render_left_sidebar_recent_view_popover from "../templates/popovers/left_sidebar_recent_view_popover.hbs";
import render_starred_messages_sidebar_actions from "../templates/starred_messages_sidebar_actions.hbs";

import * as channel from "./channel";
import * as drafts from "./drafts";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as scheduled_messages from "./scheduled_messages";
import * as settings_config from "./settings_config";
import * as starred_messages from "./starred_messages";
import * as starred_messages_ui from "./starred_messages_ui";
import * as ui_util from "./ui_util";
import * as unread_ops from "./unread_ops";
import {user_settings} from "./user_settings";

function common_click_handlers() {
    $("body").on("click", ".set-home-view", (e) => {
        e.preventDefault();
        e.preventDefault();

        const web_home_view = $(e.currentTarget).attr("data-view-code");
        const data = {web_home_view};
        channel.patch({
            url: "/json/settings",
            data,
        });

        popovers.hide_all();
    });
}
// This callback is called from the popovers on all home views
function register_mark_all_read_handler(event) {
    const {instance} = event.data;
    unread_ops.confirm_mark_all_as_read();
    popover_menus.hide_current_popover_if_visible(instance);
}

export function initialize() {
    // Starred messages popover
    popover_menus.register_popover_menu(".starred-messages-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.starred_messages = instance;
            ui_util.show_left_sidebar_menu_icon(instance.reference);

            $popper.one("click", "#unstar_all_messages", () => {
                starred_messages_ui.confirm_unstar_all_messages();
                popover_menus.hide_current_popover_if_visible(instance);
            });
            $popper.one("click", "#toggle_display_starred_msg_count", () => {
                const data = {};
                const starred_msg_counts = user_settings.starred_message_counts;
                data.starred_message_counts = JSON.stringify(!starred_msg_counts);

                channel.patch({
                    url: "/json/settings",
                    data,
                });
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onShow(instance) {
            popovers.hide_all();
            const show_unstar_all_button = starred_messages.get_count() > 0;

            instance.setContent(
                ui_util.parse_html(
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
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    // Drafts popover
    popover_menus.register_popover_menu(".drafts-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.addClass("drafts-popover");
            popover_menus.popover_instances.drafts = instance;
            ui_util.show_left_sidebar_menu_icon(instance.reference);

            $popper.one("click", "#delete_all_drafts_sidebar", () => {
                drafts.confirm_delete_all_drafts();
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onShow(instance) {
            popovers.hide_all();

            instance.setContent(ui_util.parse_html(render_drafts_sidebar_actions({})));
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.drafts = undefined;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    // Inbox popover
    popover_menus.register_popover_menu(".inbox-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.left_sidebar_inbox_popover = instance;
            ui_util.show_left_sidebar_menu_icon(instance.reference);

            $popper.one(
                "click",
                "#mark_all_messages_as_read",
                {instance},
                register_mark_all_read_handler,
            );
        },
        onShow(instance) {
            popovers.hide_all();
            const view_code = settings_config.web_home_view_values.inbox.code;
            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_inbox_popover({
                        is_home_view: user_settings.web_home_view === view_code,
                        view_code,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_inbox_popover = undefined;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    // Combined feed popover
    popover_menus.register_popover_menu(".all-messages-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.one(
                "click",
                "#mark_all_messages_as_read",
                {instance},
                register_mark_all_read_handler,
            );
        },
        onShow(instance) {
            popover_menus.popover_instances.left_sidebar_all_messages_popover = instance;
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();
            const view_code = settings_config.web_home_view_values.all_messages.code;
            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_all_messages_popover({
                        is_home_view: user_settings.web_home_view === view_code,
                        view_code,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_all_messages_popover = undefined;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    // Recent view popover
    popover_menus.register_popover_menu(".recent-view-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            $popper.one(
                "click",
                "#mark_all_messages_as_read",
                {instance},
                register_mark_all_read_handler,
            );
        },
        onShow(instance) {
            popover_menus.popover_instances.left_sidebar_recent_view_popover = instance;
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();
            const view_code = settings_config.web_home_view_values.recent_topics.code;
            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_recent_view_popover({
                        is_home_view: user_settings.web_home_view === view_code,
                        view_code,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_recent_view_popover = undefined;
            ui_util.hide_left_sidebar_menu_icon();
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
                ui_util.parse_html(
                    render_left_sidebar_condensed_views_popover({has_scheduled_messages}),
                ),
            );
        },
        onMount() {
            ui_util.update_unread_count_in_dom(
                $(".condensed-views-popover-menu-drafts"),
                drafts.draft_model.getDraftCount(),
            );
            ui_util.update_unread_count_in_dom(
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
