import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_delete_topic_modal from "../templates/confirm_dialog/confirm_delete_topic.hbs";
import render_left_sidebar_topic_actions_popover from "../templates/popovers/left_sidebar/left_sidebar_topic_actions_popover.hbs";

import * as clipboard_handler from "./clipboard_handler.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as hash_util from "./hash_util.ts";
import {$t_html} from "./i18n.ts";
import * as message_edit from "./message_edit.ts";
import * as message_summary from "./message_summary.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popover_menus_data from "./popover_menus_data.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import {realm} from "./state_data.ts";
import * as stream_popover from "./stream_popover.ts";
import * as ui_util from "./ui_util.ts";
import * as unread_ops from "./unread_ops.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

function get_conversation(instance: tippy.Instance): {
    stream_id: number;
    topic_name: string;
    url: string;
} {
    let stream_id;
    let topic_name;
    let url;

    if (instance.reference.classList.contains("recipient-bar-control")) {
        const $elt = $(instance.reference);
        const $message_header = $elt.closest(".message_header").expectOne();
        stream_id = Number.parseInt($message_header.attr("data-stream-id")!, 10);
        topic_name = $message_header.attr("data-topic-name")!;
        const topic_narrow_url = hash_util.by_stream_topic_url(stream_id, topic_name);
        url = new URL(topic_narrow_url, realm.realm_url).href;
    } else if (!instance.reference.classList.contains("topic-sidebar-menu-icon")) {
        const $elt = $(instance.reference);
        stream_id = Number.parseInt($elt.attr("data-stream-id")!, 10);
        topic_name = $elt.attr("data-topic-name")!;
        url = new URL($elt.attr("data-topic-url")!, realm.realm_url).href;
    } else {
        const $elt = $(instance.reference).closest(".topic-sidebar-menu-icon").expectOne();
        const $stream_li = $elt.closest(".narrow-filter").expectOne();
        topic_name = $elt.closest("li").expectOne().attr("data-topic-name")!;
        url = util.the($elt.closest("li").find<HTMLAnchorElement>("a.topic-box")).href;
        stream_id = stream_popover.elem_to_stream_id($stream_li);
    }

    return {stream_id, topic_name, url};
}

export function initialize(): void {
    popover_menus.register_popover_menu(
        "#stream_filters .topic-sidebar-menu-icon, .inbox-row .inbox-topic-menu, .recipient-row-topic-menu, .recent_view_focusable .visibility-status-icon",
        {
            ...popover_menus.left_sidebar_tippy_options,
            onShow(instance) {
                popover_menus.popover_instances.topics_menu = instance;
                ui_util.show_left_sidebar_menu_icon(instance.reference);
                popover_menus.on_show_prep(instance);

                const context = popover_menus_data.get_topic_popover_content_context(
                    get_conversation(instance),
                );
                instance.setContent(
                    ui_util.parse_html(render_left_sidebar_topic_actions_popover(context)),
                );
            },
            onMount(instance) {
                const $popper = $(instance.popper);
                const {stream_id, topic_name, url} = get_conversation(instance);
                const context = popover_menus_data.get_topic_popover_content_context({
                    stream_id,
                    topic_name,
                    url,
                });
                const is_topic_empty = context.is_topic_empty;
                const topic_display_name = context.topic_display_name;
                const is_empty_string_topic = context.is_empty_string_topic;

                const $elt = $(instance.reference).closest(".recent_view_focusable");
                if ($elt.length === 1) {
                    $elt.addClass("topic-popover-visible");
                }

                if (!stream_id) {
                    popover_menus.hide_current_popover_if_visible(instance);
                    return;
                }

                $popper.on("change", "input[name='sidebar-topic-visibility-select']", (e) => {
                    const start_time = Date.now();
                    const visibility_policy = Number.parseInt(
                        $(e.currentTarget).attr("data-visibility-policy")!,
                        10,
                    );

                    const success_cb = (): void => {
                        setTimeout(
                            () => {
                                popover_menus.hide_current_popover_if_visible(instance);
                            },
                            util.get_remaining_time(start_time, 500),
                        );
                    };

                    const error_cb = (): void => {
                        const prev_visibility_policy = user_topics.get_topic_visibility_policy(
                            stream_id,
                            topic_name,
                        );
                        const $prev_visibility_policy_input = $(e.currentTarget)
                            .parent()
                            .find(`input[data-visibility-policy="${prev_visibility_policy}"]`);
                        setTimeout(
                            () => {
                                $prev_visibility_policy_input.prop("checked", true);
                            },
                            util.get_remaining_time(start_time, 500),
                        );
                    };

                    user_topics.set_user_topic_visibility_policy(
                        stream_id,
                        topic_name,
                        visibility_policy,
                        false,
                        false,
                        undefined,
                        success_cb,
                        error_cb,
                    );
                });

                if (is_topic_empty) {
                    return;
                }

                $popper.one("click", ".sidebar-popover-unstar-all-in-topic", () => {
                    starred_messages_ui.confirm_unstar_all_messages_in_topic(stream_id, topic_name);
                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-mark-topic-read", () => {
                    unread_ops.mark_topic_as_read(stream_id, topic_name);
                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-mark-topic-unread", () => {
                    unread_ops.mark_topic_as_unread(stream_id, topic_name);
                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-delete-topic-messages", () => {
                    const html_body = render_delete_topic_modal({
                        topic_display_name,
                        is_empty_string_topic,
                    });

                    confirm_dialog.launch({
                        html_heading: $t_html({defaultMessage: "Delete topic"}),
                        help_link: "/help/delete-a-topic",
                        html_body,
                        on_click() {
                            message_edit.delete_topic(stream_id, topic_name);
                        },
                    });

                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-summarize-topic", () => {
                    message_summary.get_narrow_summary(stream_id, topic_name);

                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-toggle-resolved", () => {
                    message_edit.with_first_message_id(stream_id, topic_name, (message_id) => {
                        assert(message_id !== undefined);
                        message_edit.toggle_resolve_topic(message_id, topic_name, true);
                    });

                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-move-topic-messages", () => {
                    void stream_popover.build_move_topic_to_stream_popover(
                        stream_id,
                        topic_name,
                        false,
                    );
                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.one("click", ".sidebar-popover-rename-topic-messages", () => {
                    void stream_popover.build_move_topic_to_stream_popover(
                        stream_id,
                        topic_name,
                        true,
                    );
                    popover_menus.hide_current_popover_if_visible(instance);
                });

                $popper.on("click", ".sidebar-popover-copy-link-to-topic", (e) => {
                    assert(e.currentTarget instanceof HTMLElement);
                    clipboard_handler.popover_copy_link_to_clipboard(instance, $(e.currentTarget));
                });
            },
            onHidden(instance) {
                const $elt = $(instance.reference).closest(".recent_view_focusable");
                if ($elt.length === 1) {
                    $elt.removeClass("topic-popover-visible");
                }
                instance.destroy();
                popover_menus.popover_instances.topics_menu = null;
                ui_util.hide_left_sidebar_menu_icon();
            },
        },
    );
}
