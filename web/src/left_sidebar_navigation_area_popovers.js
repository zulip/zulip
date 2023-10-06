import $ from "jquery";

import render_drafts_sidebar_actions from "../templates/drafts_sidebar_action.hbs";
import render_left_sidebar_inbox_popover from "../templates/popovers/left_sidebar_inbox_popover.hbs";
import render_starred_messages_sidebar_actions from "../templates/starred_messages_sidebar_actions.hbs";

import * as channel from "./channel";
import * as drafts from "./drafts";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import * as starred_messages from "./starred_messages";
import * as starred_messages_ui from "./starred_messages_ui";
import {parse_html} from "./ui_util";
import * as unread_ops from "./unread_ops";
import {user_settings} from "./user_settings";

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
            instance.setContent(parse_html(render_left_sidebar_inbox_popover()));
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_inbox_popover = undefined;
        },
    });
}
