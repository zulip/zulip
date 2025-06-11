import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_left_sidebar_all_messages_popover from "../templates/popovers/left_sidebar/left_sidebar_all_messages_popover.hbs";
import render_left_sidebar_condensed_views_popover from "../templates/popovers/left_sidebar/left_sidebar_condensed_views_popover.hbs";
import render_left_sidebar_drafts_popover from "../templates/popovers/left_sidebar/left_sidebar_drafts_popover.hbs";
import render_left_sidebar_inbox_popover from "../templates/popovers/left_sidebar/left_sidebar_inbox_popover.hbs";
import render_left_sidebar_recent_view_popover from "../templates/popovers/left_sidebar/left_sidebar_recent_view_popover.hbs";
import render_left_sidebar_starred_messages_popover from "../templates/popovers/left_sidebar/left_sidebar_starred_messages_popover.hbs";
import render_navigation_view_hide_popover from "../templates/popovers/left_sidebar/navigation_view_hide_popover.hbs";

import * as channel from "./channel.ts";
import * as drafts from "./drafts.ts";
import * as navigation_views from "./navigation_views.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as settings_config from "./settings_config.ts";
import * as starred_messages from "./starred_messages.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import {user_settings} from "./user_settings.ts";

function common_click_handlers(): void {
    $("body").on("click", ".set-home-view", (e) => {
        e.preventDefault();

        const web_home_view = $(e.currentTarget).attr("data-view-code");
        const data = {web_home_view};
        void channel.patch({
            url: "/json/settings",
            data,
        });

        popovers.hide_all();
    });

    $("body").on("click", ".hide-navigation-view", (e) => {
        e.preventDefault();

        const fragment = $(e.currentTarget).attr("data-fragment");
        if (!fragment) {
            return;
        }

        navigation_views.set_view_pinned_status(fragment, false);

        popovers.hide_all();
    });
}

function register_mark_all_read_handler(
    event: JQuery.ClickEvent<
        tippy.PopperElement,
        {
            instance: tippy.Instance;
        }
    >,
): void {
    const {instance} = event.data;
    unread_ops.confirm_mark_all_as_read();
    popover_menus.hide_current_popover_if_visible(instance);
}

export function initialize(): void {
    // Starred messages popover
    popover_menus.register_popover_menu(".starred-messages-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.starred_messages = instance;
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);

            $popper.one("click", "#unstar_all_messages", () => {
                starred_messages_ui.confirm_unstar_all_messages();
                popover_menus.hide_current_popover_if_visible(instance);
            });
            $popper.one("click", "#toggle_display_starred_msg_count", () => {
                const starred_msg_counts = user_settings.starred_message_counts;
                const data = {
                    starred_message_counts: JSON.stringify(!starred_msg_counts),
                };
                void channel.patch({
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
                    render_left_sidebar_starred_messages_popover({
                        show_unstar_all_button,
                        starred_message_counts: user_settings.starred_message_counts,
                        fragment: settings_config.built_in_views_values.starred_messages.fragment,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.starred_messages = null;
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
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);

            $popper.one("click", "#delete_all_drafts_sidebar", () => {
                drafts.confirm_delete_all_drafts();
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onShow(instance) {
            popovers.hide_all();

            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_drafts_popover({
                        fragment: settings_config.built_in_views_values.drafts.fragment,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.drafts = null;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    // Inbox popover
    popover_menus.register_popover_menu(".inbox-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.left_sidebar_inbox_popover = instance;
            assert(instance.reference instanceof HTMLElement);
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
                        fragment: settings_config.built_in_views_values.inbox.fragment,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_inbox_popover = null;
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
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();
            const view_code = settings_config.web_home_view_values.all_messages.code;
            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_all_messages_popover({
                        is_home_view: user_settings.web_home_view === view_code,
                        view_code,
                        fragment: settings_config.built_in_views_values.all_messages.fragment,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_all_messages_popover = null;
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
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();
            const view_code = settings_config.web_home_view_values.recent_topics.code;
            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_recent_view_popover({
                        is_home_view: user_settings.web_home_view === view_code,
                        view_code,
                        fragment: settings_config.built_in_views_values.recent_view.fragment,
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_recent_view_popover = null;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    popover_menus.register_popover_menu(".mentions-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onShow(instance) {
            popover_menus.popover_instances.left_sidebar_mentions_popover = instance;
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();

            instance.setContent(
                ui_util.parse_html(
                    render_navigation_view_hide_popover({
                        fragment: settings_config.built_in_views_values.mentions.fragment,
                        hide_text: "Hide mentions",
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_mentions_popover = null;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    popover_menus.register_popover_menu(".reactions-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onShow(instance) {
            popover_menus.popover_instances.left_sidebar_reactions_popover = instance;
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();

            instance.setContent(
                ui_util.parse_html(
                    render_navigation_view_hide_popover({
                        fragment: settings_config.built_in_views_values.my_reactions.fragment,
                        hide_text: "Hide reactions",
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_reactions_popover = null;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    popover_menus.register_popover_menu(".scheduled_messages-sidebar-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onShow(instance) {
            popover_menus.popover_instances.left_sidebar_scheduled_messages_popover = instance;
            assert(instance.reference instanceof HTMLElement);
            ui_util.show_left_sidebar_menu_icon(instance.reference);
            popovers.hide_all();

            instance.setContent(
                ui_util.parse_html(
                    render_navigation_view_hide_popover({
                        fragment: settings_config.built_in_views_values.scheduled_messages.fragment,
                        hide_text: "Hide scheduled messages",
                    }),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.left_sidebar_scheduled_messages_popover = null;
            ui_util.hide_left_sidebar_menu_icon();
        },
    });

    popover_menus.register_popover_menu(".left-sidebar-navigation-menu-icon", {
        ...popover_menus.left_sidebar_tippy_options,
        onShow(instance) {
            const is_condensed = $("#views-label-container").hasClass(
                "showing-condensed-navigation",
            );
            const is_has_scheduled_messages = scheduled_messages.get_count() > 0;
            let all_built_in_views = navigation_views.get_built_in_views();

            if (!is_has_scheduled_messages && !is_condensed) {
                all_built_in_views = all_built_in_views.filter(
                    (view) =>
                        view.fragment !==
                        settings_config.built_in_views_values.scheduled_messages.fragment,
                );
            }

            popovers.hide_all();
            instance.setContent(
                ui_util.parse_html(
                    render_left_sidebar_condensed_views_popover({
                        is_condensed,
                        has_scheduled_messages: is_has_scheduled_messages,
                        views: all_built_in_views.filter((view) => !view.is_pinned),
                    }),
                ),
            );
        },
        onMount() {
            const all_built_in_views = navigation_views
                .get_built_in_views()
                .filter((view) => !view.is_pinned);

            for (const view of all_built_in_views) {
                let count = 0;
                switch (view.fragment) {
                    case settings_config.built_in_views_values.drafts.fragment:
                        count = drafts.draft_model.getDraftCount();
                        break;
                    case settings_config.built_in_views_values.scheduled_messages.fragment:
                        count = scheduled_messages.get_count();
                        break;
                    case settings_config.built_in_views_values.starred_messages.fragment:
                        count = starred_messages.get_count();
                        break;
                    case settings_config.built_in_views_values.inbox.fragment:
                    case settings_config.built_in_views_values.recent_view.fragment:
                    case settings_config.built_in_views_values.all_messages.fragment:
                        count = unread.get_counts().home_unread_messages;
                        break;
                    case settings_config.built_in_views_values.mentions.fragment:
                        count = unread.get_counts().mentioned_message_count;
                        break;
                }

                ui_util.update_unread_count_in_dom(
                    $(`.views-popover-menu-${view.css_class_suffix}`),
                    count,
                );
            }
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.top_left_sidebar = null;
        },
    });

    common_click_handlers();
}
