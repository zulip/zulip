"use strict";

const render_all_messages_sidebar_actions = require("../templates/all_messages_sidebar_actions.hbs");
const render_delete_topic_modal = require("../templates/delete_topic_modal.hbs");
const render_move_topic_to_stream = require("../templates/move_topic_to_stream.hbs");
const render_starred_messages_sidebar_actions = require("../templates/starred_messages_sidebar_actions.hbs");
const render_stream_sidebar_actions = require("../templates/stream_sidebar_actions.hbs");
const render_topic_sidebar_actions = require("../templates/topic_sidebar_actions.hbs");
const render_unstar_messages_modal = require("../templates/unstar_messages_modal.hbs");

// We handle stream popovers and topic popovers in this
// module.  Both are popped up from the left sidebar.
let current_stream_sidebar_elem;
let current_topic_sidebar_elem;
let all_messages_sidebar_elem;
let starred_messages_sidebar_elem;

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

exports.stream_sidebar_menu_handle_keyboard = (key) => {
    const items = get_popover_menu_items(current_stream_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
};

exports.topic_sidebar_menu_handle_keyboard = (key) => {
    const items = get_popover_menu_items(current_topic_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
};

exports.all_messages_sidebar_menu_handle_keyboard = (key) => {
    const items = get_popover_menu_items(all_messages_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
};

exports.starred_messages_sidebar_menu_handle_keyboard = (key) => {
    const items = get_popover_menu_items(starred_messages_sidebar_elem);
    popovers.popover_items_handle_keyboard(key, items);
};

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

exports.stream_popped = function () {
    return current_stream_sidebar_elem !== undefined;
};

exports.topic_popped = function () {
    return current_topic_sidebar_elem !== undefined;
};

exports.all_messages_popped = function () {
    return all_messages_sidebar_elem !== undefined;
};

exports.starred_messages_popped = function () {
    return starred_messages_sidebar_elem !== undefined;
};

exports.hide_stream_popover = function () {
    if (exports.stream_popped()) {
        $(current_stream_sidebar_elem).popover("destroy");
        current_stream_sidebar_elem = undefined;
    }
};

exports.hide_topic_popover = function () {
    if (exports.topic_popped()) {
        $(current_topic_sidebar_elem).popover("destroy");
        current_topic_sidebar_elem = undefined;
    }
};

exports.hide_all_messages_popover = function () {
    if (exports.all_messages_popped()) {
        $(all_messages_sidebar_elem).popover("destroy");
        all_messages_sidebar_elem = undefined;
    }
};

exports.hide_starred_messages_popover = function () {
    if (exports.starred_messages_popped()) {
        $(starred_messages_sidebar_elem).popover("destroy");
        starred_messages_sidebar_elem = undefined;
    }
};

// These are the only two functions that is really shared by the
// two popovers, so we could split out topic stuff to
// another module pretty easily.
exports.show_streamlist_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

exports.hide_streamlist_sidebar = function () {
    $(".app-main .column-left").removeClass("expanded");
};

function stream_popover_sub(e) {
    const elem = $(e.currentTarget).parents("ul");
    const stream_id = elem_to_stream_id(elem);
    const sub = stream_data.get_sub_by_id(stream_id);
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

function build_stream_popover(opts) {
    const elt = opts.elt;
    const stream_id = opts.stream_id;

    if (exports.stream_popped() && current_stream_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        exports.hide_stream_popover();
        return;
    }

    popovers.hide_all();
    exports.show_streamlist_sidebar();

    const content = render_stream_sidebar_actions({
        stream: stream_data.get_sub_by_id(stream_id),
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

    if (exports.topic_popped() && current_topic_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        exports.hide_topic_popover();
        return;
    }

    const sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error("cannot build topic popover for stream: " + stream_id);
        return;
    }

    popovers.hide_all();
    exports.show_streamlist_sidebar();

    const is_muted = muting.is_topic_muted(sub.stream_id, topic_name);
    const can_mute_topic = !is_muted;
    const can_unmute_topic = is_muted;

    const content = render_topic_sidebar_actions({
        stream_name: sub.name,
        stream_id: sub.stream_id,
        topic_name,
        can_mute_topic,
        can_unmute_topic,
        is_realm_admin: sub.is_realm_admin,
        color: sub.color,
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

    if (exports.all_messages_popped() && all_messages_sidebar_elem === elt) {
        exports.hide_all_messages_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();

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

    if (exports.starred_messages_popped() && starred_messages_sidebar_elem === elt) {
        exports.hide_starred_messages_popover();
        e.stopPropagation();
        return;
    }

    popovers.hide_all();

    const content = render_starred_messages_sidebar_actions({
        starred_message_counts: page_params.starred_message_counts,
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
    const available_streams = stream_data
        .subscribed_subs()
        .filter((s) => s.stream_id !== current_stream_id);
    const current_stream_name = stream_data.maybe_get_stream_name(current_stream_id);
    const args = {
        available_streams,
        topic_name,
        current_stream_id,
        current_stream_name,
        notify_new_thread: message_edit.notify_new_thread_default,
        notify_old_thread: message_edit.notify_old_thread_default,
    };

    exports.hide_topic_popover();

    $("#move-a-topic-modal-holder").html(render_move_topic_to_stream(args));

    const stream_header_colorblock = $(".topic_stream_edit_header").find(
        ".stream_header_colorblock",
    );
    ui_util.decorate_stream_bar(current_stream_name, stream_header_colorblock, false);
    $("#select_stream_id").on("change", function () {
        const stream_name = stream_data.maybe_get_stream_name(Number.parseInt(this.value, 10));
        ui_util.decorate_stream_bar(stream_name, stream_header_colorblock, false);
    });

    $("#move_topic_modal").modal("show");
}

exports.register_click_handlers = function () {
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

        build_topic_popover({
            elt,
            stream_id,
            topic_name,
        });
    });

    $("#global_filters").on("click", ".all-messages-sidebar-menu-icon", build_all_messages_popover);

    $("#global_filters").on(
        "click",
        ".starred-messages-sidebar-menu-icon",
        build_starred_messages_popover,
    );

    exports.register_stream_handlers();
    exports.register_topic_handlers();
};

exports.register_stream_handlers = function () {
    // Stream settings
    $("body").on("click", ".open_stream_settings", (e) => {
        const sub = stream_popover_sub(e);
        exports.hide_stream_popover();

        const stream_edit_hash = hash_util.stream_edit_uri(sub);
        hashchange.go_to_location(stream_edit_hash);
    });

    // Pin/unpin
    $("body").on("click", ".pin_to_top", (e) => {
        const sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        subs.toggle_pin_to_top_stream(sub);
        e.stopPropagation();
    });

    // Mark all messages in stream as read
    $("body").on("click", ".mark_stream_as_read", (e) => {
        const sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        unread_ops.mark_stream_as_read(sub.stream_id);
        e.stopPropagation();
    });

    // Mark all messages as read
    $("body").on("click", "#mark_all_messages_as_read", (e) => {
        exports.hide_all_messages_popover();
        unread_ops.mark_all_as_read();
        e.stopPropagation();
    });

    // Unstar all messages
    $("body").on("click", "#unstar_all_messages", (e) => {
        exports.hide_starred_messages_popover();
        e.preventDefault();
        e.stopPropagation();
        $(".left-sidebar-modal-holder").empty();
        $(".left-sidebar-modal-holder").html(render_unstar_messages_modal());
        $("#unstar-messages-modal").modal("show");
    });

    $("body").on("click", "#do_unstar_messages_button", (e) => {
        $("#unstar-messages-modal").modal("hide");
        message_flags.unstar_all_messages();
        e.stopPropagation();
    });

    // Toggle displaying starred message count
    $("body").on("click", "#toggle_display_starred_msg_count", (e) => {
        exports.hide_starred_messages_popover();
        e.preventDefault();
        e.stopPropagation();
        const starred_msg_counts = page_params.starred_message_counts;
        const data = {};
        data.starred_message_counts = JSON.stringify(!starred_msg_counts);
        channel.patch({
            url: "/json/settings/display",
            data,
        });
    });
    // Mute/unmute
    $("body").on("click", ".toggle_stream_muted", (e) => {
        const sub = stream_popover_sub(e);
        exports.hide_stream_popover();
        subs.set_muted(sub, !sub.is_muted);
        e.stopPropagation();
    });

    // Unsubscribe
    $("body").on("click", ".popover_sub_unsub_button", function (e) {
        $(this).toggleClass("unsub");
        $(this).closest(".popover").fadeOut(500).delay(500).remove();

        const sub = stream_popover_sub(e);
        subs.sub_or_unsub(sub);
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
            exports.hide_stream_popover();
        });
        if ($(window).width() <= 768) {
            $(".popover-inner").hide().fadeIn(300);
            $(".popover").addClass("colorpicker-popover");
        }
    });
};

function topic_popover_sub(e) {
    const stream_id = topic_popover_stream_id(e);
    if (!stream_id) {
        blueslip.error("cannot find stream id");
        return undefined;
    }

    const sub = stream_data.get_sub_by_id(stream_id);
    if (!sub) {
        blueslip.error("Unknown stream: " + stream_id);
        return undefined;
    }
    return sub;
}

exports.register_topic_handlers = function () {
    // Narrow to topic
    $("body").on("click", ".narrow_to_topic", (e) => {
        exports.hide_topic_popover();

        const sub = topic_popover_sub(e);
        if (!sub) {
            return;
        }

        const topic = $(e.currentTarget).attr("data-topic-name");

        const operators = [
            {operator: "stream", operand: sub.name},
            {operator: "topic", operand: topic},
        ];
        narrow.activate(operators, {trigger: "sidebar"});

        e.stopPropagation();
    });

    // Mute the topic
    $("body").on("click", ".sidebar-popover-mute-topic", (e) => {
        const stream_id = topic_popover_stream_id(e);
        if (!stream_id) {
            return;
        }

        const topic = $(e.currentTarget).attr("data-topic-name");
        muting_ui.mute_topic(stream_id, topic);
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
        muting_ui.unmute_topic(stream_id, topic);
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
        exports.hide_topic_popover();
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

        exports.hide_topic_popover();

        $("#delete-topic-modal-holder").html(render_delete_topic_modal(args));

        $("#do_delete_topic_button").on("click", () => {
            message_edit.delete_topic(stream_id, topic);
        });

        $("#delete_topic_modal").modal("show");

        e.stopPropagation();
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

        const {old_topic_name, select_stream_id} = params;
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
                {operator: "stream", operand: current_stream_id},
                {operator: "topic", operand: old_topic_name},
            ]),
        };

        message_edit.show_topic_move_spinner();
        channel.get({
            url: "/json/messages",
            data,
            idempotent: true,
            success(data) {
                const message_id = data.messages[0].id;

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
            error(xhr) {
                message_edit.hide_topic_move_spinner();
                show_error_msg(xhr.responseJSON.msg);
            },
        });
    });
};

window.stream_popover = exports;
