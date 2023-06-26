/* Compose box module responsible for the message's recipient */

import $ from "jquery";
import _ from "lodash";

import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";

import * as compose_banner from "./compose_banner";
import * as compose_fade from "./compose_fade";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as compose_validate from "./compose_validate";
import * as dropdown_widget from "./dropdown_widget";
import {$t} from "./i18n";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import * as stream_bar from "./stream_bar";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as ui_util from "./ui_util";
import * as util from "./util";

// selected_recipient_id is the current state for the stream picker widget:
// "" -> stream message but no stream is selected
// integer -> stream id of the selected stream.
// "direct" -> Direct message is selected.
export let selected_recipient_id = "";
export const DIRECT_MESSAGE_ID = "direct";

export function set_selected_recipient_id(recipient_id) {
    selected_recipient_id = recipient_id;
    on_compose_select_recipient_update();
}

function composing_to_current_topic_narrow() {
    return (
        util.lower_same(compose_state.stream_name(), narrow_state.stream_name() || "") &&
        util.lower_same(compose_state.topic(), narrow_state.topic() || "")
    );
}

function composing_to_current_private_message_narrow() {
    const compose_state_recipient = compose_state.private_message_recipient();
    const narrow_state_recipient = narrow_state.pm_emails_string();
    return (
        compose_state_recipient &&
        narrow_state_recipient &&
        _.isEqual(
            compose_state_recipient
                .split(",")
                .map((s) => s.trim())
                .sort(),
            narrow_state_recipient
                .split(",")
                .map((s) => s.trim())
                .sort(),
        )
    );
}

export function update_narrow_to_recipient_visibility() {
    const message_type = compose_state.get_message_type();
    if (message_type === "stream") {
        const stream_exists = Boolean(compose_state.stream_id());

        if (
            stream_exists &&
            !composing_to_current_topic_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".narrow_to_compose_recipients").toggleClass("invisible", false);
            return;
        }
    } else if (message_type === "private") {
        const recipients = compose_state.private_message_recipient();
        if (
            recipients &&
            !composing_to_current_private_message_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".narrow_to_compose_recipients").toggleClass("invisible", false);
            return;
        }
    }
    $(".narrow_to_compose_recipients").toggleClass("invisible", true);
}

function update_fade() {
    if (!compose_state.composing()) {
        return;
    }

    const msg_type = compose_state.get_message_type();

    // It's possible that the new topic is not a resolved topic
    // so we clear the older warning.
    compose_validate.clear_topic_resolved_warning();

    compose_validate.warn_if_topic_resolved();
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_all();
}

export function update_on_recipient_change() {
    update_fade();
    update_narrow_to_recipient_visibility();
}

export function get_posting_policy_error_message() {
    if (selected_recipient_id === "direct") {
        if (
            page_params.realm_private_message_policy ===
            settings_config.private_message_policy_values.disabled.code
        ) {
            return $t({
                defaultMessage: "Direct messages are disabled in this organization.",
            });
        }
        return "";
    }

    const stream = sub_store.get(selected_recipient_id);
    if (stream && !stream_data.can_post_messages_in_stream(stream)) {
        return $t({
            defaultMessage: "You do not have permission to post in this stream.",
        });
    }
    return "";
}

export function check_posting_policy_for_compose_box() {
    const banner_text = get_posting_policy_error_message();
    if (banner_text === "") {
        $(".compose_right_float_container").removeClass("disabled-compose-send-button-container");
        compose_banner.clear_errors();
        return;
    }

    let banner_classname = compose_banner.CLASSNAMES.no_post_permissions;
    if (selected_recipient_id === "direct") {
        banner_classname = compose_banner.CLASSNAMES.private_messages_disabled;
    }
    $(".compose_right_float_container").addClass("disabled-compose-send-button-container");
    compose_banner.show_error_message(banner_text, banner_classname, $("#compose_banners"));
}

function switch_message_type(message_type) {
    $("#compose-content .alert").hide();

    compose_state.set_message_type(message_type);

    const opts = {
        message_type,
        stream_id: compose_state.stream_id(),
        topic: compose_state.topic(),
        private_message_recipient: compose_state.private_message_recipient(),
    };
    update_compose_for_message_type(message_type, opts);
    update_placeholder_text();
    compose_ui.set_focus(message_type, opts);
}

function update_recipient_label(stream_id) {
    const stream = stream_data.get_sub_by_id(stream_id);
    if (stream === undefined) {
        $("#compose_select_recipient_widget .dropdown_widget_value").text(
            $t({defaultMessage: "Select a stream"}),
        );
    } else {
        $("#compose_select_recipient_widget .dropdown_widget_value").html(
            render_inline_decorated_stream_name({stream, show_colored_icon: true}),
        );
    }
}

export function update_compose_for_message_type(message_type, opts) {
    if (message_type === "stream") {
        $("#compose-direct-recipient").hide();
        $("#stream_message_recipient_topic").show();
        $("#stream_toggle").addClass("active");
        $("#private_message_toggle").removeClass("active");
        $("#compose-recipient").removeClass("compose-recipient-direct-selected");
        update_recipient_label(opts.stream_id);
    } else {
        $("#compose-direct-recipient").show();
        $("#stream_message_recipient_topic").hide();
        $("#stream_toggle").removeClass("active");
        $("#private_message_toggle").addClass("active");
        $("#compose-recipient").addClass("compose-recipient-direct-selected");
        // TODO: When "Direct message" is selected, we show "DM" on the dropdown
        // button. It would be nice if the dropdown supported a way to attach
        // the "DM" button display string so we wouldn't have to manually change
        // it here.
        const direct_message_label = $t({defaultMessage: "DM"});
        $("#compose_select_recipient_widget .dropdown_widget_value").html(
            `<i class="zulip-icon zulip-icon-users stream-privacy-type-icon"></i> ${direct_message_label}`,
        );
    }
    compose_banner.clear_errors();
    compose_banner.clear_warnings();
    compose_banner.clear_uploads();
}

export function on_compose_select_recipient_update() {
    const prev_message_type = compose_state.get_message_type();

    let curr_message_type = "stream";
    if (selected_recipient_id === DIRECT_MESSAGE_ID) {
        curr_message_type = "private";
    }

    if (prev_message_type !== curr_message_type) {
        switch_message_type(curr_message_type);
    }

    if (curr_message_type === "stream") {
        // Update stream name in the recipient box.
        const $stream_header_colorblock = $(
            "#compose_select_recipient_widget_wrapper .stream_header_colorblock",
        );
        const stream_id = compose_state.stream_id();
        update_recipient_label(stream_id);
        stream_bar.decorate(stream_id, $stream_header_colorblock);
    }

    check_posting_policy_for_compose_box();
    update_on_recipient_change();
}

export function possibly_update_stream_name_in_compose(stream_id) {
    if (selected_recipient_id === stream_id) {
        on_compose_select_recipient_update();
    }
}

function item_click_callback(event, dropdown) {
    let recipient_id = $(event.currentTarget).attr("data-unique-id");
    if (recipient_id !== DIRECT_MESSAGE_ID) {
        recipient_id = Number.parseInt(recipient_id, 10);
    }
    set_selected_recipient_id(recipient_id);
    dropdown.hide();
    event.preventDefault();
    event.stopPropagation();
}

function get_options_for_recipient_widget() {
    const options = stream_data.get_options_for_dropdown_widget();

    const direct_messages_option = {
        is_direct_message: true,
        unique_id: DIRECT_MESSAGE_ID,
        name: $t({defaultMessage: "Direct message"}),
    };

    if (
        page_params.realm_private_message_policy ===
        settings_config.private_message_policy_values.by_anyone.code
    ) {
        options.unshift(direct_messages_option);
    } else {
        options.push(direct_messages_option);
    }
    return options;
}

function compose_recipient_dropdown_on_show(dropdown) {
    // Offset to display dropdown above compose.
    let top_offset = 5;
    const window_height = window.innerHeight;
    const search_box_and_padding_height = 50;
    // pixels above compose box.
    const recipient_input_top = $("#compose_select_recipient_widget_wrapper").get_offset_to_window()
        .top;
    const top_space = recipient_input_top - top_offset - search_box_and_padding_height;
    // pixels below compose starting from top of compose box.
    const bottom_space = window_height - recipient_input_top - search_box_and_padding_height;
    // Show dropdown on top / bottom based on available space.
    let placement = "top-start";
    if (bottom_space > top_space) {
        placement = "bottom-start";
        top_offset = -30;
    }
    const offset = [-10, top_offset];
    dropdown.setProps({placement, offset});
    const height = Math.min(
        dropdown_widget.DEFAULT_DROPDOWN_HEIGHT,
        Math.max(top_space, bottom_space),
    );
    const $popper = $(dropdown.popper);
    $popper.find(".dropdown-list-wrapper").css("max-height", height + "px");
}

export function open_compose_recipient_dropdown() {
    $("#compose_select_recipient_widget").trigger("click");
}

function focus_compose_recipient() {
    $("#compose_select_recipient_widget_wrapper").trigger("focus");
}

// NOTE: Since tippy triggers this on `mousedown` it is always triggered before say a `click` on `textarea`.
function on_hidden_callback() {
    if (compose_state.get_message_type() === "stream") {
        // Always move focus to the topic input even if it's not empty,
        // since it's likely the user will want to update the topic
        // after updating the stream.
        ui_util.place_caret_at_end($("#stream_message_recipient_topic")[0]);
    } else {
        if (compose_state.private_message_recipient().length === 0) {
            $("#private_message_recipient").trigger("focus").trigger("select");
        } else {
            $("#compose-textarea").trigger("focus");
        }
    }
}

export function initialize() {
    new dropdown_widget.DropdownWidget({
        widget_name: "compose_select_recipient",
        get_options: get_options_for_recipient_widget,
        item_click_callback,
        $events_container: $("body"),
        on_show_callback: compose_recipient_dropdown_on_show,
        on_exit_with_escape_callback: focus_compose_recipient,
        // We want to focus on topic box if dropdown was closed via selecting an item.
        focus_target_on_hidden: false,
        on_hidden_callback,
    }).setup();

    // `keyup` isn't relevant for streams since it registers as a change only
    // when an item in the dropdown is selected.
    $("#stream_message_recipient_topic,#private_message_recipient").on(
        "keyup",
        update_on_recipient_change,
    );
    // changes for the stream dropdown are handled in on_compose_select_recipient_update
    $("#stream_message_recipient_topic,#private_message_recipient").on("change", () => {
        update_on_recipient_change();
        compose_state.set_recipient_edited_manually(true);
    });
}

export function update_placeholder_text() {
    // Change compose placeholder text only if compose box is open.
    if (!$("#compose-textarea").is(":visible")) {
        return;
    }

    const opts = {
        message_type: compose_state.get_message_type(),
        stream_id: compose_state.stream_id(),
        topic: compose_state.topic(),
        // TODO: to remove a circular import, direct message recipient needs
        // to be calculated in compose_state instead of compose_pm_pill.
        private_message_recipient: compose_pm_pill.get_emails(),
    };

    $("#compose-textarea").attr("placeholder", compose_ui.compute_placeholder_text(opts));
}
