import $ from "jquery";

import render_move_topic_to_stream from "../templates/move_topic_to_stream.hbs";
import render_stream_sidebar_actions from "../templates/stream_sidebar_actions.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as compose_actions from "./compose_actions";
import * as composebox_typeahead from "./composebox_typeahead";
import * as dialog_widget from "./dialog_widget";
import {DropdownListWidget} from "./dropdown_list_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as message_edit from "./message_edit";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as settings_data from "./settings_data";
import * as stream_bar from "./stream_bar";
import * as stream_color from "./stream_color";
import * as stream_settings_ui from "./stream_settings_ui";
import * as sub_store from "./sub_store";
import * as ui_report from "./ui_report";
import * as ui_util from "./ui_util";
import * as unread_ops from "./unread_ops";
// We handle stream popovers and topic popovers in this
// module.  Both are popped up from the left sidebar.
let current_stream_sidebar_elem;
let stream_widget;
let $stream_header_colorblock;

// Keep the menu icon over which the popover is based off visible.
function show_left_sidebar_menu_icon(element) {
    $(element).closest("[class*='-sidebar-menu-icon']").addClass("left_sidebar_menu_icon_visible");
}

// Remove the class from element when popover is closed
function hide_left_sidebar_menu_icon() {
    $(".left_sidebar_menu_icon_visible").removeClass("left_sidebar_menu_icon_visible");
}

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

export function elem_to_stream_id($elem) {
    const stream_id = Number.parseInt($elem.attr("data-stream-id"), 10);

    if (stream_id === undefined) {
        blueslip.error("could not find stream id");
    }

    return stream_id;
}

export function stream_popped() {
    return current_stream_sidebar_elem !== undefined;
}

export function hide_stream_popover() {
    if (stream_popped()) {
        $(current_stream_sidebar_elem).popover("destroy");
        hide_left_sidebar_menu_icon();
        current_stream_sidebar_elem = undefined;
    }
}

export function show_streamlist_sidebar() {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_stream_filters_container();
}

export function hide_streamlist_sidebar() {
    $(".app-main .column-left").removeClass("expanded");
}

function stream_popover_sub(e) {
    const $elem = $(e.currentTarget).parents("ul");
    const stream_id = elem_to_stream_id($elem);
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.error("Unknown stream", {stream_id});
        return undefined;
    }
    return sub;
}

// This little function is a workaround for the fact that
// Bootstrap popovers don't properly handle being resized --
// so after resizing our popover to add in the spectrum color
// picker, we need to adjust its height accordingly.
function update_spectrum($popover, update_func) {
    const initial_height = $popover[0].offsetHeight;

    const $colorpicker = $popover.find(".colorpicker-container").find(".colorpicker");
    update_func($colorpicker);
    const after_height = $popover[0].offsetHeight;

    const $popover_root = $popover.closest(".popover");
    const current_top_px = Number.parseFloat($popover_root.css("top").replace("px", ""));
    const height_delta = after_height - initial_height;
    let top = current_top_px - height_delta / 2;

    if (top < 0) {
        top = 0;
        $popover_root.find("div.arrow").hide();
    } else if (top + after_height > $(window).height() - 20) {
        top = $(window).height() - after_height - 20;
        if (top < 0) {
            top = 0;
        }
        $popover_root.find("div.arrow").hide();
    }

    $popover_root.css("top", top + "px");
}

function build_stream_popover(opts) {
    const elt = opts.elt;
    const stream_id = opts.stream_id;

    if (stream_popped() && current_stream_sidebar_elem === elt) {
        // If the popover is already shown, clicking again should toggle it.
        hide_stream_popover();
        return;
    }

    popovers.hide_all_except_sidebars();

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
    const $popover = $(`.streams_popover[data-stream-id="${CSS.escape(stream_id)}"]`);

    update_spectrum($popover, ($colorpicker) => {
        $colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options);
    });

    current_stream_sidebar_elem = elt;
    show_left_sidebar_menu_icon(elt);
}

export function build_move_topic_to_stream_popover(
    current_stream_id,
    topic_name,
    only_topic_edit,
    message,
) {
    const current_stream_name = sub_store.maybe_get_stream_name(current_stream_id);
    const args = {
        topic_name,
        current_stream_id,
        notify_new_thread: message_edit.notify_new_thread_default,
        notify_old_thread: message_edit.notify_old_thread_default,
        from_message_actions_popover: message !== undefined,
        only_topic_edit,
    };

    // When the modal is opened for moving the whole topic from left sidebar,
    // we do not have any message object and so we disable the stream input
    // based on the move_messages_between_streams_policy setting and topic
    // input based on edit_topic_policy. In other cases, message object is
    // available and thus we check the time-based permissions as well in the
    // below if block to enable or disable the stream and topic input.
    let disable_stream_input = !settings_data.user_can_move_messages_between_streams();
    args.disable_topic_input = !settings_data.user_can_move_messages_to_another_topic();

    let modal_heading;
    if (only_topic_edit) {
        modal_heading = $t_html({defaultMessage: "Rename topic"});
    } else {
        modal_heading = $t_html({defaultMessage: "Move topic"});
    }

    if (message !== undefined) {
        modal_heading = $t_html({defaultMessage: "Move messages"});
        // We disable topic input only for modal is opened from the message actions
        // popover and not when moving the whole topic from left sidebar. This is
        // because topic editing permission depend on message and we do not have
        // any message object when opening the modal and the first message of
        // topic is fetched from the server after clicking submit.
        // Though, this will be changed soon as we are going to make topic
        // edit permission independent of message.

        // We potentially got to this function by clicking a button that implied the
        // user would be able to move their message.  Give a little bit of buffer in
        // case the button has been around for a bit, e.g. we show the
        // move_message_button (hovering plus icon) as long as the user would have
        // been able to click it at the time the mouse entered the message_row. Also
        // a buffer in case their computer is slow, or stalled for a second, etc
        // If you change this number also change edit_limit_buffer in
        // zerver.actions.message_edit.check_update_message
        const move_limit_buffer = 5;
        args.disable_topic_input = !message_edit.is_topic_editable(message, move_limit_buffer);
        disable_stream_input = !message_edit.is_stream_editable(message, move_limit_buffer);
    }

    function get_params_from_form() {
        return Object.fromEntries(
            $("#move_topic_form")
                .serializeArray()
                .map(({name, value}) => [name, value]),
        );
    }

    function update_submit_button_disabled_state(select_stream_id) {
        const {current_stream_id, new_topic_name, old_topic_name} = get_params_from_form();

        // Unlike most topic comparisons in Zulip, we intentionally do
        // a case-sensitive comparison, since adjusting the
        // capitalization of a topic is a valid operation.
        // new_topic_name can be undefined when the new topic input is
        // disabled in case when user does not have permission to edit
        // topic and thus submit button is disabled if stream is also
        // not changed.
        $("#move_topic_modal .dialog_submit_button")[0].disabled =
            Number.parseInt(current_stream_id, 10) === Number.parseInt(select_stream_id, 10) &&
            (new_topic_name === undefined || new_topic_name.trim() === old_topic_name.trim());
    }

    function move_topic() {
        const params = get_params_from_form();

        const {old_topic_name} = params;
        let select_stream_id;
        if (only_topic_edit) {
            select_stream_id = undefined;
        } else {
            select_stream_id = stream_widget.value();
        }

        let {
            current_stream_id,
            new_topic_name,
            send_notification_to_new_thread,
            send_notification_to_old_thread,
        } = params;
        send_notification_to_new_thread = send_notification_to_new_thread === "on";
        send_notification_to_old_thread = send_notification_to_old_thread === "on";
        current_stream_id = Number.parseInt(current_stream_id, 10);

        if (new_topic_name !== undefined) {
            // new_topic_name can be undefined when the new topic input is disabled when
            // user does not have permission to edit topic.
            new_topic_name = new_topic_name.trim();
        }
        if (old_topic_name.trim() === new_topic_name) {
            // We use `undefined` to tell the server that
            // there has been no change in the topic name.
            new_topic_name = undefined;
        }
        if (select_stream_id === current_stream_id) {
            // We use `undefined` to tell the server that
            // there has been no change in stream. This is
            // important for cases when changing stream is
            // not allowed or when changes other than
            // stream-change has been made.
            select_stream_id = undefined;
        }

        let propagate_mode = "change_all";
        if (message !== undefined) {
            // We already have the message_id here which means that modal is opened using
            // message popover.
            propagate_mode = $("#move_topic_modal select.message_edit_topic_propagate").val();
            message_edit.move_topic_containing_message_to_stream(
                message.id,
                select_stream_id,
                new_topic_name,
                send_notification_to_new_thread,
                send_notification_to_old_thread,
                propagate_mode,
            );
            return;
        }

        dialog_widget.show_dialog_spinner();
        message_edit.with_first_message_id(
            current_stream_id,
            old_topic_name,
            (message_id) => {
                message_edit.move_topic_containing_message_to_stream(
                    message_id,
                    select_stream_id,
                    new_topic_name,
                    send_notification_to_new_thread,
                    send_notification_to_old_thread,
                    propagate_mode,
                );
            },
            (xhr) => {
                dialog_widget.hide_dialog_spinner();
                ui_report.error(
                    $t_html({defaultMessage: "Error moving topic"}),
                    xhr,
                    $("#move_topic_modal #dialog_error"),
                );
            },
        );
    }

    function set_stream_topic_typeahead() {
        const $topic_input = $("#move_topic_form .move_messages_edit_topic");
        const new_stream_id = Number(stream_widget.value(), 10);
        const new_stream_name = sub_store.get(new_stream_id).name;
        $topic_input.data("typeahead").unlisten();
        composebox_typeahead.initialize_topic_edit_typeahead($topic_input, new_stream_name, false);
    }

    function move_topic_on_update() {
        update_submit_button_disabled_state(stream_widget.value());
        set_stream_topic_typeahead();
    }

    function move_topic_post_render() {
        $("#move_topic_modal .dialog_submit_button").prop("disabled", true);

        const $topic_input = $("#move_topic_form .move_messages_edit_topic");
        composebox_typeahead.initialize_topic_edit_typeahead(
            $topic_input,
            current_stream_name,
            false,
        );

        if (only_topic_edit) {
            // Set select_stream_id to current_stream_id since we user is not allowed
            // to edit stream in topic-edit only UI.
            const select_stream_id = current_stream_id;
            $topic_input.on("input", () => {
                update_submit_button_disabled_state(select_stream_id);
            });
            return;
        }

        $stream_header_colorblock = $("#dialog_widget_modal .topic_stream_edit_header").find(
            ".stream_header_colorblock",
        );
        stream_bar.decorate(current_stream_name, $stream_header_colorblock);
        const streams_list =
            message_edit.get_available_streams_for_moving_messages(current_stream_id);
        const opts = {
            widget_name: "select_stream",
            data: streams_list,
            default_text: $t({defaultMessage: "No streams"}),
            include_current_item: false,
            value: current_stream_id,
            on_update: move_topic_on_update,
        };
        stream_widget = new DropdownListWidget(opts);

        stream_widget.setup();

        $("#select_stream_widget .dropdown-toggle").prop("disabled", disable_stream_input);
        $("#move_topic_modal .move_messages_edit_topic").on("input", () => {
            update_submit_button_disabled_state(stream_widget.value());
        });
    }

    function focus_on_move_modal_render() {
        if (!disable_stream_input && args.disable_topic_input) {
            $("#select_stream_widget .button").trigger("focus");
        } else {
            ui_util.place_caret_at_end($(".move_messages_edit_topic")[0]);
        }
    }

    dialog_widget.launch({
        html_heading: modal_heading,
        html_body: render_move_topic_to_stream(args),
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
        id: "move_topic_modal",
        on_click: move_topic,
        loading_spinner: true,
        on_shown: focus_on_move_modal_render,
        post_render: move_topic_post_render,
    });
}

export function register_click_handlers() {
    $("#stream_filters").on("click", ".stream-sidebar-menu-icon", (e) => {
        e.stopPropagation();

        const elt = e.target;
        const $stream_li = $(elt).parents("li");
        const stream_id = elem_to_stream_id($stream_li);

        build_stream_popover({
            elt,
            stream_id,
        });
    });

    $("body").on("click keypress", ".move-topic-dropdown .list_item", (e) => {
        // We want the dropdown to collapse once any of the list item is pressed
        // and thus don't want to kill the natural bubbling of event.
        e.preventDefault();

        if (e.type === "keypress" && !keydown_util.is_enter_event(e)) {
            return;
        }
        const stream_name = sub_store.maybe_get_stream_name(
            Number.parseInt(stream_widget.value(), 10),
        );

        stream_bar.decorate(stream_name, $stream_header_colorblock);
    });

    register_stream_handlers();
}

export function register_stream_handlers() {
    // Stream settings
    $("body").on("click", ".open_stream_settings", (e) => {
        const sub = stream_popover_sub(e);
        hide_stream_popover();

        const stream_edit_hash = hash_util.stream_edit_url(sub);
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
        update_spectrum($(e.target).closest(".streams_popover"), ($colorpicker) => {
            $(".colorpicker-container").show();
            $colorpicker.spectrum("destroy");
            $colorpicker.spectrum(stream_color.sidebar_popover_colorpicker_options_full);
            // In theory this should clean up the old color picker,
            // but this seems a bit flaky -- the new colorpicker
            // doesn't fire until you click a button, but the buttons
            // have been hidden.  We work around this by just manually
            // fixing it up here.
            $colorpicker.parent().find(".sp-container").removeClass("sp-buttons-disabled");
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
