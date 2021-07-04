import ClipboardJS from "clipboard";
import $ from "jquery";

import render_all_messages_sidebar_actions from "../templates/all_messages_sidebar_actions.hbs";
import render_delete_topic_modal from "../templates/confirm_dialog/confirm_delete_topic.hbs";
import render_move_topic_to_stream from "../templates/move_topic_to_stream.hbs";
import render_starred_messages_sidebar_actions from "../templates/starred_messages_sidebar_actions.hbs";
import render_stream_sidebar_actions from "../templates/stream_sidebar_actions.hbs";
import render_topic_sidebar_actions from "../templates/topic_sidebar_actions.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as confirm_dialog from "./confirm_dialog";
import {DropdownListWidget} from "./dropdown_list_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as message_edit from "./message_edit";
import * as muted_topics from "./muted_topics";
import * as muted_topics_ui from "./muted_topics_ui";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as settings_data from "./settings_data";
import * as starred_messages from "./starred_messages";
import * as starred_messages_ui from "./starred_messages_ui";
import * as stream_bar from "./stream_bar";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_settings_ui from "./stream_settings_ui";
import * as sub_store from "./sub_store";
import * as unread_ops from "./unread_ops";
import {user_settings} from "./user_settings";

// We handle stream popovers and topic popovers in this
// module.  Both are popped up from the left sidebar.
let current_stream_sidebar_elem;
let current_topic_sidebar_elem;
let all_messages_sidebar_elem;
let starred_messages_sidebar_elem;
let stream_widget;
let stream_header_colorblock;

function get_popover_menu_items(sidebar_elem) {
    if (!sidebar_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = $(sidebar_elem).data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for stream sidebar menu.");
        return undefined;
    }
    return $("li:not(.divider):visible > a", popover_data.$tip);
}

export function stream_sidebar_menu_handle_keyboard(key) {
    const items = get_popover_menu_items(current_stream_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
}

export function topic_sidebar_menu_handle_keyboard(key) {
    const items = get_popover_menu_items(current_topic_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
}

export function all_messages_sidebar_menu_handle_keyboard(key) {
    const items = get_popover_menu_items(all_messages_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
}

export function starred_messages_sidebar_menu_handle_keyboard(key) {
    const items = get_popover_menu_items(starred_messages_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
}

function elem_to_stream_id(elem) {
    const stream_id = Number.parseInt(elem.attr("data-stream-id"), 10);

    if (stream_id === undefined) {
        blueslip.error("could not find stream id");
    }

    return stream_id;
}

function topic_popover_stream_id(e) {
    return elem_to_stream_id($(e.currentTarget));
}

export function stream_popped() {
    return current_stream_sidebar_elem !== undefined;
}

export function topic_popped() {
    return current_topic_sidebar_elem !== undefined;
}

export function all_messages_popped() {
    return all_messages_sidebar_elem !== undefined;
}

export function starred_messages_popped() {
    return starred_messages_sidebar_elem !== undefined;
}

export function hide_stream_popover() {
    if (stream_popped()) {
        $(current_stream_sidebar_elem).popover("destroy");
        current_stream_sidebar_elem = undefined;
    }
}

export function hide_topic_popover() {
    if (topic_popped()) {
        $(current_topic_sidebar_elem).popover("destroy");
        current_topic_sidebar_elem = undefined;
    }
}

export function hide_all_messages_popover() {
    if (all_messages_popped()) {
        $(all_messages_sidebar_elem).popover("destroy");
        all_messages_sidebar_elem = undefined;
    }
}

export function hide_starred_messages_popover() {
    if (starred_messages_popped()) {
        $(starred_messages_sidebar_elem).popover("destroy");
        starred_messages_sidebar_elem = undefined;
    }
}

// These are the only two functions that is really shared by the
// two popovers, so we could split out topic stuff to
// another module pretty easily.
export function show_streamlist_sidebar() {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
}

export function hide_streamlist_sidebar() {
    $(".app-main .column-left").removeClass("expanded");
}

function stream_popover_sub(e) {
    const elem = $(e.currentTarget).parents("ul");
    const stream_id = elem_to_stream_id(elem);
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("Unknown stream: " + stream_id);
        return undefined;
    }
    return sub;
}

// This little function is a workaround for the fact that
// Bootstrap popovers don't properly handle being resized --
// so after resizing our popover to add in the spectrum color
// picker, we need to adjust its height accordingly.
function update_spectrum(popover, update_func) {
    const initial_height = popover[0].offsetHeight;

    const colorpicker = popover.find(".colorpicker-container").find(".colorpicker");
    update_func(colorpicker);
    const after_height = popover[0].offsetHeight;

    const popover_root = popover.closest(".popover");
    const current_top_px = Number.parseFloat(popover_root.css("top").replace("px", ""));
    const height_delta = after_height - initial_height;
    let top = current_top_px - height_delta / 2;

    if (top < 0) {
        top = 0;
        popover_root.find("div.arrow").hide();
    } else if (top + after_height > $(window).height() - 20) {
        top = $(window).height() - after_height - 20;
        if (top < 0) {
            top = 0;
        }
        popover_root.find("div.arrow").hide();
    }

    popover_root.css("top", top + "px");
}

// Builds the `Copy link to topic` topic action.
function build_topic_link_clipboard(url) {
    if (!url) {
        return;
    }

    const copy_event = new ClipboardJS(".sidebar-popover-copy-link-to-topic", {
        text() {
            return url;
        },
    });

    // Hide the topic popover once the url is successfully
    // copied to clipboard.
    copy_event.on("success", () => {
        hide_topic_popover();
    });
}

function build_stream_popover(opts) {
    const elt = opts.elt;
    const stream_id = opts.stream_id;

    if (stream_popped() && current_stream_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        hide_stream_popover();
        return;
    }

    popovers.hide_all();
    show_streamlist_sidebar();

    const content = render_stream_sidebar_actions({
        stream: sub_store.get(stream_id),
    });

    $(elt).popover({
        content,
        html: true,
        trigger: "manual",
        fixed: true,
        fix_positions: true,
    });

    $(elt).popover("show");
    const popover = $(`.streams_popover[data-stream-id="${CSS.escape(stream_id)}"]`);

    update_spectrum(popover, (colorpicker) => {
        colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options);
    });

    current_stream_sidebar_elem = elt;
}

function build_topic_popover(opts) {
    const elt = opts.elt;
    const stream_id = opts.stream_id;
    const topic_name = opts.topic_name;

    if (topic_popped() && current_topic_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        hide_topic_popover();
        return;
    }

    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("cannot build topic popover for stream: " + stream_id);
        return;
    }

    popovers.hide_all();
    show_streamlist_sidebar();

    const topic_muted = muted_topics.is_topic_muted(sub.stream_id, topic_name);
    const has_starred_messages = starred_messages.get_count_in_topic(sub.stream_id, topic_name) > 0;
    // Arguably, we could offer the "Move topic" option even if users
    // can only edit the name within a stream.
    const can_move_topic = settings_data.user_can_move_messages_between_streams();

    const content = render_topic_sidebar_actions({
        stream_name: sub.name,
        stream_id: sub.stream_id,
        topic_name,
        topic_muted,
        can_move_topic,
        is_realm_admin: page_params.is_admin,
        topic_is_resolved: topic_name.startsWith(message_edit.RESOLVED_TOPIC_PREFIX),
        color: sub.color,
        has_starred_messages,
    });

    $(elt).popover({
        content,
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");

    current_topic_sidebar_elem = elt;
}

function build_all_messages_popover(e) {
    const elt = e.target;

    if (all_messages_popped() && all_messages_sidebar_elem === elt) {
        hide_all_messages_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();
    show_streamlist_sidebar();

    const content = render_all_messages_sidebar_actions();

    $(elt).popover({
        content,
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");
    all_messages_sidebar_elem = elt;
    e.stopPropagation();
}

function build_starred_messages_popover(e) {
    const elt = e.target;

    if (starred_messages_popped() && starred_messages_sidebar_elem === elt) {
        hide_starred_messages_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();
    show_streamlist_sidebar();

    const show_unstar_all_button = starred_messages.get_count() > 0;
    const content = render_starred_messages_sidebar_actions({
        show_unstar_all_button,
        starred_message_counts: user_settings.starred_message_counts,
    });

    $(elt).popover({
        content,
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $(elt).popover("show");
    starred_messages_sidebar_elem = elt;
    e.stopPropagation();
}

function build_move_topic_to_stream_popover(e, current_stream_id, topic_name) {
    // TODO: Add support for keyboard-alphabet navigation. Some orgs
    // many streams and scrolling can be a painful process in that
    // case.
    //
    // NOTE: Private streams are also included in this list.  We
    // likely will make it possible to move messages to/from private
    // streams in the future.
    const current_stream_name = stream_data.maybe_get_stream_name(current_stream_id);
    const args = {
        topic_name,
        current_stream_id,
        notify_new_thread: message_edit.notify_new_thread_default,
        notify_old_thread: message_edit.notify_old_thread_default,
    };

    const streams_list = stream_data.subscribed_subs().map((stream) => ({
        name: stream.name,
        value: stream.stream_id.toString(),
    }));
    const opts = {
        widget_name: "select_stream",
        data: streams_list,
        default_text: $t({defaultMessage: "No streams"}),
        include_current_item: false,
        value: current_stream_id,
    };

    hide_topic_popover();

    $("#move-a-topic-modal-holder").html(render_move_topic_to_stream(args));

    stream_widget = new DropdownListWidget(opts);
    stream_header_colorblock = $("#move_topic_modal .topic_stream_edit_header").find(
        ".stream_header_colorblock",
    );

    stream_bar.decorate(current_stream_name, stream_header_colorblock, false);
    overlays.open_modal("#move_topic_modal");
}

export function register_click_handlers() {
    $("#stream_filters").on("click", ".stream-sidebar-menu-icon", (e) => {
        e.stopPropagation();

        const elt = e.target;
        const stream_li = $(elt).parents("li");
        const stream_id = elem_to_stream_id(stream_li);

        build_stream_popover({
            elt,
            stream_id,
        });
    });

    $("#stream_filters").on("click", ".topic-sidebar-menu-icon", (e) => {
        e.stopPropagation();

        const elt = $(e.target).closest(".topic-sidebar-menu-icon").expectOne()[0];
        const stream_li = $(elt).closest(".narrow-filter").expectOne();
        const stream_id = elem_to_stream_id(stream_li);
        const topic_name = $(elt).closest("li").expectOne().attr("data-topic-name");
        const url = $(elt).closest("li").find(".topic-name").expectOne().prop("href");

        build_topic_popover({
            elt,
            stream_id,
            topic_name,
        });

        build_topic_link_clipboard(url);
    });

    $("#global_filters").on("click", ".all-messages-sidebar-menu-icon", build_all_messages_popover);

    $("#global_filters").on(
        "click",
        ".starred-messages-sidebar-menu-icon",
        build_starred_messages_popover,
    );

    $("body").on("click keypress", ".move-topic-dropdown .list_item", (e) => {
        // We want the dropdown to collapse once any of the list item is pressed
        // and thus don't want to kill the natural bubbling of event.
        e.preventDefault();

        if (e.type === "keypress" && e.key !== "Enter") {
            return;
        }
        const stream_name = stream_data.maybe_get_stream_name(
            Number.parseInt(stream_widget.value(), 10),
        );

        stream_bar.decorate(stream_name, stream_header_colorblock, false);
    });

    register_stream_handlers();
    register_topic_handlers();
}

export function register_stream_handlers() {
    // Stream settings
    $("body").on("click", ".open_stream_settings", (e) => {
        const sub = stream_popover_sub(e);
        hide_stream_popover();

        const stream_edit_hash = hash_util.stream_edit_uri(sub);
        browser_history.go_to_location(stream_edit_hash);
    });

    // Pin/unpin
    $("body").on("click", ".pin_to_top", (e) => {
        const sub = stream_popover_sub(e);
        hide_stream_popover();
        stream_settings_ui.toggle_pin_to_top_stream(sub);
        e.stopPropagation();
    });

    // Mark all messages in stream as read
    $("body").on("click", ".mark_stream_as_read", (e) => {
        const sub = stream_popover_sub(e);
        hide_stream_popover();
        unread_ops.mark_stream_as_read(sub.stream_id);
        e.stopPropagation();
    });

    // Mark all messages as read
    $("body").on("click", "#mark_all_messages_as_read", (e) => {
        hide_all_messages_popover();
        unread_ops.mark_all_as_read();
        e.stopPropagation();
    });

    // Unstar all messages
    $("body").on("click", "#unstar_all_messages", (e) => {
        hide_starred_messages_popover();
        e.preventDefault();
        e.stopPropagation();
        starred_messages_ui.confirm_unstar_all_messages();
    });

    // Unstar all messages in topic
    $("body").on("click", ".sidebar-popover-unstar-all-in-topic", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const topic_name = $(".sidebar-popover-unstar-all-in-topic").attr("data-topic-name");
        const stream_id = $(".sidebar-popover-unstar-all-in-topic").attr("data-stream-id");
        hide_topic_popover();
        starred_messages_ui.confirm_unstar_all_messages_in_topic(
            Number.parseInt(stream_id, 10),
            topic_name,
        );
    });

    // Toggle displaying starred message count
    $("body").on("click", "#toggle_display_starred_msg_count", (e) => {
        hide_starred_messages_popover();
        e.preventDefault();
        e.stopPropagation();
        const starred_msg_counts = user_settings.starred_message_counts;
        const data = {};
        data.starred_message_counts = JSON.stringify(!starred_msg_counts);
        channel.patch({
            url: "/json/settings",
            data,
        });
    });
    // Mute/unmute
    $("body").on("click", ".toggle_stream_muted", (e) => {
        const sub = stream_popover_sub(e);
        hide_stream_popover();
        stream_settings_ui.set_muted(sub, !sub.is_muted);
        e.stopPropagation();
    });

    // New topic in stream menu
    $("body").on("click", ".popover_new_topic_button", (e) => {
        const sub = stream_popover_sub(e);
        hide_stream_popover();

        compose_actions.start("stream", {
            trigger: "popover new topic button",
            stream: sub.name,
            topic: "",
        });
        e.preventDefault();
        e.stopPropagation();
    });

    // Unsubscribe
    $("body").on("click", ".popover_sub_unsub_button", function (e) {
        $(this).toggleClass("unsub");
        $(this).closest(".popover").fadeOut(500).delay(500).remove();

        const sub = stream_popover_sub(e);
        stream_settings_ui.sub_or_unsub(sub);
        e.preventDefault();
        e.stopPropagation();
    });

    // Choose a different color.
    $("body").on("click", ".choose_stream_color", (e) => {
        update_spectrum($(e.target).closest(".streams_popover"), (colorpicker) => {
            $(".colorpicker-container").show();
            colorpicker.spectrum("destroy");
            colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options_full);
            // In theory this should clean up the old color picker,
            // but this seems a bit flaky -- the new colorpicker
            // doesn't fire until you click a button, but the buttons
            // have been hidden.  We work around this by just manually
            // fixing it up here.
            colorpicker.parent().find(".sp-container").removeClass("sp-buttons-disabled");
            $(e.target).hide();
        });

        $(".streams_popover").on("click", "a.sp-cancel", () => {
            hide_stream_popover();
        });
        if ($(window).width() <= 768) {
            $(".popover-inner").hide().fadeIn(300);
            $(".popover").addClass("colorpicker-popover");
        }
    });
}

function with_first_message_id(stream_id, topic_name, success_cb, error_cb) {
    // The API endpoint for editing messages to change their
    // content, topic, or stream requires a message ID.
    //
    // Because we don't have full data in the browser client, it's
    // possible that we might display a topic in the left sidebar
    // (and thus expose the UI for moving its topic to another
    // stream) without having a message ID that is definitely
    // within the topic.  (The comments in stream_topic_history.js
    // discuss the tricky issues around message deletion that are
    // involved here).
    //
    // To ensure this option works reliably at a small latency
    // cost for a rare operation, we just ask the server for the
    // latest message ID in the topic.
    const data = {
        anchor: "newest",
        num_before: 1,
        num_after: 0,
        narrow: JSON.stringify([
            {operator: "stream", operand: stream_id},
            {operator: "topic", operand: topic_name},
        ]),
    };

    channel.get({
        url: "/json/messages",
        data,
        idempotent: true,
        success(data) {
            const message_id = data.messages[0].id;
            success_cb(message_id);
        },
        error_cb,
    });
}

export function register_topic_handlers() {
    // Mute the topic
    $("body").on("click", ".sidebar-popover-mute-topic", (e) => {
        const stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        const topic = $(e.currentTarget).attr("data-topic-name");
        muted_topics_ui.mute_topic(stream_id, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    // Unmute the topic
    $("body").on("click", ".sidebar-popover-unmute-topic", (e) => {
        const stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        const topic = $(e.currentTarget).attr("data-topic-name");
        muted_topics_ui.unmute_topic(stream_id, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    // Mark all messages as read
    $("body").on("click", ".sidebar-popover-mark-topic-read", (e) => {
        const stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        const topic = $(e.currentTarget).attr("data-topic-name");
        hide_topic_popover();
        unread_ops.mark_topic_as_read(stream_id, topic);
        e.stopPropagation();
    });

    // Deleting all message in a topic
    $("body").on("click", ".sidebar-popover-delete-topic-messages", (e) => {
        const stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        const topic = $(e.currentTarget).attr("data-topic-name");
        const args = {
            topic_name: topic,
        };

        hide_topic_popover();

        const html_body = render_delete_topic_modal(args);

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete topic"}),
            help_link: "/help/delete-a-topic",
            html_body,
            on_click: () => {
                message_edit.delete_topic(stream_id, topic);
            },
        });

        e.stopPropagation();
    });

    $("body").on("click", ".sidebar-popover-toggle-resolved", (e) => {
        const topic_row = $(e.currentTarget);
        const stream_id = Number.parseInt(topic_row.attr("data-stream-id"), 10);
        const topic_name = topic_row.attr("data-topic-name");
        with_first_message_id(stream_id, topic_name, (message_id) => {
            message_edit.toggle_resolve_topic(message_id, topic_name);
        });

        hide_topic_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".sidebar-popover-move-topic-messages", (e) => {
        const topic_row = $(e.currentTarget);
        const stream_id = Number.parseInt(topic_row.attr("data-stream-id"), 10);
        const topic_name = topic_row.attr("data-topic-name");
        build_move_topic_to_stream_popover(e, stream_id, topic_name);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", "#topic_stream_edit_form_error .send-status-close", () => {
        $("#topic_stream_edit_form_error").hide();
    });

    $("body").on("click", "#do_move_topic_button", (e) => {
        e.preventDefault();

        function show_error_msg(msg) {
            $("#topic_stream_edit_form_error .error-msg").text(msg);
            $("#topic_stream_edit_form_error").show();
        }

        const params = Object.fromEntries(
            $("#move_topic_form")
                .serializeArray()
                .map(({name, value}) => [name, value]),
        );

        const {old_topic_name} = params;
        const select_stream_id = stream_widget.value();

        let {
            current_stream_id,
            new_topic_name,
            send_notification_to_new_thread,
            send_notification_to_old_thread,
        } = params;
        new_topic_name = new_topic_name.trim();
        send_notification_to_new_thread = send_notification_to_new_thread === "on";
        send_notification_to_old_thread = send_notification_to_old_thread === "on";
        current_stream_id = Number.parseInt(current_stream_id, 10);

        if (
            current_stream_id === Number.parseInt(select_stream_id, 10) &&
            new_topic_name.toLowerCase() === old_topic_name.toLowerCase()
        ) {
            show_error_msg("Please select a different stream or change topic name.");
            return;
        }

        message_edit.show_topic_move_spinner();
        with_first_message_id(
            current_stream_id,
            old_topic_name,
            (message_id) => {
                if (old_topic_name.trim() === new_topic_name.trim()) {
                    // We use `undefined` to tell the server that
                    // there has been no change in the topic name.
                    new_topic_name = undefined;
                }

                if (old_topic_name && select_stream_id) {
                    message_edit.move_topic_containing_message_to_stream(
                        message_id,
                        select_stream_id,
                        new_topic_name,
                        send_notification_to_new_thread,
                        send_notification_to_old_thread,
                    );
                }
            },
            (xhr) => {
                message_edit.hide_topic_move_spinner();
                show_error_msg(xhr.responseJSON.msg);
            },
        );
    });
}
