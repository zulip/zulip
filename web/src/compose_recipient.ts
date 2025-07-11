/* Compose box module responsible for the message's recipient */

import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";

import * as compose_banner from "./compose_banner.ts";
import * as compose_fade from "./compose_fade.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import type {ComposeTriggeredOptions} from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import * as drafts from "./drafts.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidget, Option} from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import {realm} from "./state_data.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as ui_util from "./ui_util.ts";
import * as user_groups from "./user_groups.ts";
import * as util from "./util.ts";

type MessageType = "stream" | "private";

let compose_select_recipient_dropdown_widget: DropdownWidget;

function composing_to_current_topic_narrow(): boolean {
    // If the narrow state's stream ID is undefined, then
    // the user cannot be composing to a current topic narrow.
    if (narrow_state.stream_id() === undefined) {
        return false;
    }
    return (
        compose_state.stream_id() === narrow_state.stream_id() &&
        util.lower_same(compose_state.topic(), narrow_state.topic() ?? "")
    );
}

function composing_to_current_private_message_narrow(): boolean {
    const compose_state_recipient = new Set(compose_state.private_message_recipient_ids());
    const narrow_state_recipient = narrow_state.pm_ids_set();
    if (narrow_state_recipient.size === 0) {
        return false;
    }
    return _.isEqual(narrow_state_recipient, compose_state_recipient);
}

export let update_recipient_row_attention_level = (): void => {
    // We need to adjust the privacy-icon colors in the low-attention state
    const message_type = compose_state.get_message_type();
    if (message_type === "stream") {
        const stream_id = compose_state.stream_id();
        const channel_picker_icon_selector =
            "#compose_select_recipient_widget .channel-privacy-type-icon";

        stream_color.adjust_stream_privacy_icon_colors(stream_id, channel_picker_icon_selector);
    }

    // We're piggy-backing here, in a roundabout way, on
    // compose_ui.set_focus(). Any time the topic or DM recipient
    // row is focused, that puts us outside the low-attention
    // recipient-row state--including the `c` hotkey or the
    // Start new conversation button being clicked.
    const is_compose_textarea_focused = document.activeElement?.id === "compose-textarea";
    if (
        is_compose_textarea_focused &&
        (composing_to_current_topic_narrow() || composing_to_current_private_message_narrow()) &&
        compose_state.has_full_recipient() &&
        !compose_state.is_recipient_edited_manually()
    ) {
        $("#compose-recipient").toggleClass("low-attention-recipient-row", true);
    } else {
        $("#compose-recipient").toggleClass("low-attention-recipient-row", false);
    }
};

export function rewire_update_recipient_row_attention_level(
    value: typeof update_recipient_row_attention_level,
): void {
    update_recipient_row_attention_level = value;
}

export function set_high_attention_recipient_row(): void {
    $("#compose-recipient").removeClass("low-attention-recipient-row");
}

export let update_narrow_to_recipient_visibility = (): void => {
    const message_type = compose_state.get_message_type();
    if (message_type === "stream") {
        const stream_exists = Boolean(compose_state.stream_id());

        if (
            stream_exists &&
            !composing_to_current_topic_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".conversation-arrow").toggleClass("narrow_to_compose_recipients", true);
            return;
        }
    } else if (message_type === "private") {
        const recipients = compose_state.private_message_recipient_ids();
        if (
            recipients.length > 0 &&
            !composing_to_current_private_message_narrow() &&
            compose_state.has_full_recipient()
        ) {
            $(".conversation-arrow").toggleClass("narrow_to_compose_recipients", true);
            return;
        }
    }
    $(".conversation-arrow").toggleClass("narrow_to_compose_recipients", false);
};

export function rewire_update_narrow_to_recipient_visibility(
    value: typeof update_narrow_to_recipient_visibility,
): void {
    update_narrow_to_recipient_visibility = value;
}

function update_fade(): void {
    if (!compose_state.composing()) {
        return;
    }

    const msg_type = compose_state.get_message_type();

    // It's possible that the new topic is not a resolved topic
    // so we clear the older warning.
    compose_validate.clear_topic_resolved_warning();

    compose_validate.warn_if_topic_resolved(true);
    compose_fade.set_focused_recipient(msg_type);
    compose_fade.update_all();
}

export function update_on_recipient_change(): void {
    update_fade();
    update_narrow_to_recipient_visibility();
    compose_validate.warn_if_guest_in_dm_recipient();
    update_recipient_row_attention_level();
    drafts.update_compose_draft_count();
    check_posting_policy_for_compose_box();
    compose_validate.validate_and_update_send_button_status();

    // Clear the topic moved banner when the recipient
    // is changed or compose box is closed.
    compose_validate.clear_topic_moved_info();
}

export let check_posting_policy_for_compose_box = (): void => {
    const banner_text = compose_validate.get_posting_policy_error_message();
    if (banner_text === "") {
        compose_banner.clear_errors();
        return;
    }

    let banner_classname = compose_banner.CLASSNAMES.no_post_permissions;
    if (compose_state.selected_recipient_id === "direct") {
        banner_classname = compose_banner.CLASSNAMES.cannot_send_direct_message;
        compose_banner.cannot_send_direct_message_error(banner_text);
    } else {
        compose_banner.show_error_message(banner_text, banner_classname, $("#compose_banners"));
    }
};

export function rewire_check_posting_policy_for_compose_box(
    value: typeof check_posting_policy_for_compose_box,
): void {
    check_posting_policy_for_compose_box = value;
}

function switch_message_type(message_type: MessageType): void {
    $("#compose-content .alert").hide();

    compose_state.set_message_type(message_type);

    const opts = {
        message_type,
        trigger: "switch_message_type",
        stream_id: compose_state.stream_id()!,
        topic: compose_state.topic(),
        private_message_recipient_ids: compose_state.private_message_recipient_ids(),
    };
    update_compose_for_message_type(opts);
    update_compose_area_placeholder_text();
    compose_ui.set_focus(opts);
}

function update_recipient_label(stream_id?: number): void {
    const stream = stream_id !== undefined ? stream_data.get_sub_by_id(stream_id) : undefined;
    if (stream === undefined) {
        const select_channel_label = $t({defaultMessage: "Select a channel"});
        $("#compose_select_recipient_widget .dropdown_widget_value").html(
            `<span class="select-channel-label">${select_channel_label}</span>`,
        );
    } else {
        $("#compose_select_recipient_widget .dropdown_widget_value").html(
            render_inline_decorated_channel_name({stream, show_colored_icon: true}),
        );
    }
}

export function update_compose_for_message_type(opts: ComposeTriggeredOptions): void {
    if (opts.message_type === "stream") {
        $("#compose-direct-recipient").hide();
        $("#compose_recipient_box").show();
        $("#stream_toggle").addClass("active");
        $("#private_message_toggle").removeClass("active");
        $("#compose-recipient").removeClass("compose-recipient-direct-selected");
        update_recipient_label(opts.stream_id);
    } else {
        $("#compose-direct-recipient").show();
        $("#compose_recipient_box").hide();
        $("#stream_toggle").removeClass("active");
        $("#private_message_toggle").addClass("active");
        $("#compose-recipient").addClass("compose-recipient-direct-selected");
        // TODO: When "Direct message" is selected, we show "DM" on the dropdown
        // button. It would be nice if the dropdown supported a way to attach
        // the "DM" button display string so we wouldn't have to manually change
        // it here.
        const direct_message_label = $t({defaultMessage: "DM"});
        $("#compose_select_recipient_widget .dropdown_widget_value").html(
            `<i class="zulip-icon zulip-icon-users channel-privacy-type-icon"></i>
            <span class="decorated-dm-label">${direct_message_label}</span>`,
        );
    }
    compose_banner.clear_errors();
    compose_banner.clear_warnings();
    compose_banner.clear_uploads();
    update_recipient_row_attention_level();
}

export let on_compose_select_recipient_update = (): void => {
    const prev_message_type = compose_state.get_message_type();

    let curr_message_type: MessageType = "stream";
    if (compose_state.selected_recipient_id === compose_state.DIRECT_MESSAGE_ID) {
        curr_message_type = "private";
    }

    if (prev_message_type !== curr_message_type) {
        switch_message_type(curr_message_type);
    }

    if (curr_message_type === "stream") {
        // Update stream name in the recipient box.
        const stream_id = compose_state.stream_id();
        update_recipient_label(stream_id);
    }

    update_on_recipient_change();
};

export function rewire_on_compose_select_recipient_update(
    value: typeof on_compose_select_recipient_update,
): void {
    on_compose_select_recipient_update = value;
}

export function possibly_update_stream_name_in_compose(stream_id: number): void {
    if (compose_state.selected_recipient_id === stream_id) {
        on_compose_select_recipient_update();
    }
}

function item_click_callback(event: JQuery.ClickEvent, dropdown: tippy.Instance): void {
    const recipient_id_str = $(event.currentTarget).attr("data-unique-id");
    assert(recipient_id_str !== undefined);
    let recipient_id: string | number = recipient_id_str;
    if (recipient_id !== compose_state.DIRECT_MESSAGE_ID) {
        recipient_id = Number.parseInt(recipient_id, 10);
    }
    compose_state.set_selected_recipient_id(recipient_id);
    compose_state.set_recipient_edited_manually(true);
    // Enable or disable topic input based on `topics_policy`.
    update_topic_displayed_text(compose_state.topic());
    on_compose_select_recipient_update();
    compose_select_recipient_dropdown_widget.item_clicked = true;
    dropdown.hide();
    event.preventDefault();
    event.stopPropagation();
}

function get_options_for_recipient_widget(): Option[] {
    const options: Option[] = stream_data.get_options_for_dropdown_widget();

    const direct_messages_option = {
        is_direct_message: true,
        unique_id: compose_state.DIRECT_MESSAGE_ID,
        name: $t({defaultMessage: "Direct message"}),
    };

    if (!user_groups.is_setting_group_empty(realm.realm_direct_message_permission_group)) {
        options.unshift(direct_messages_option);
    } else {
        options.push(direct_messages_option);
    }
    return options;
}

export function toggle_compose_recipient_dropdown(): void {
    $("#compose_select_recipient_widget").trigger("click");
}

function focus_compose_recipient(): void {
    $("#compose_select_recipient_widget_wrapper").trigger("focus");
}

function on_show_callback(): void {
    $("#compose_select_recipient_widget").addClass("widget-open");
}

// NOTE: Since tippy triggers this on `mousedown` it is always triggered before say a `click` on `textarea`.
function on_hidden_callback(): void {
    $("#compose_select_recipient_widget").removeClass("widget-open");
    compose_state.set_is_processing_forward_message(false);
    compose_validate.warn_if_topic_resolved(false);
    if (!compose_select_recipient_dropdown_widget.item_clicked) {
        // If the dropdown was NOT closed due to selecting an item,
        // don't do anything.
        return;
    }
    if (compose_state.get_message_type() === "stream") {
        // Always move focus to the topic input even if it's not empty,
        // since it's likely the user will want to update the topic
        // after updating the stream.
        ui_util.place_caret_at_end(util.the($("input#stream_message_recipient_topic")));
    } else {
        if (compose_state.private_message_recipient_ids().length === 0) {
            $("#private_message_recipient").trigger("focus").trigger("select");
        } else {
            $("textarea#compose-textarea").trigger("focus");
        }
    }
    compose_select_recipient_dropdown_widget.item_clicked = false;
}

export function handle_middle_pane_transition(): void {
    if (compose_state.composing()) {
        update_narrow_to_recipient_visibility();
        update_recipient_row_attention_level();
    }
}

export function initialize(): void {
    compose_select_recipient_dropdown_widget = new dropdown_widget.DropdownWidget({
        widget_name: "compose_select_recipient",
        get_options: get_options_for_recipient_widget,
        item_click_callback,
        $events_container: $("body"),
        on_exit_with_escape_callback: focus_compose_recipient,
        // We want to focus on topic box if dropdown was closed via selecting an item.
        focus_target_on_hidden: false,
        on_show_callback,
        on_hidden_callback,
        dropdown_input_visible_selector: "#compose_select_recipient_widget_wrapper",
        prefer_top_start_placement: true,
        tippy_props: {
            offset: [-10, 5],
        },
        tab_moves_focus_to_target() {
            if (compose_state.get_message_type() === "stream") {
                return "#stream_message_recipient_topic";
            }
            return "#private_message_recipient";
        },
    });
    compose_select_recipient_dropdown_widget.setup();

    // changes for the stream dropdown are handled in on_compose_select_recipient_update
    $("#stream_message_recipient_topic,#private_message_recipient").on("input change", () => {
        // To make sure the checks in update_on_recipient_change() are correct,
        // we update manual editing first.
        compose_state.set_recipient_edited_manually(true);
        update_on_recipient_change();
    });

    $("#private_message_recipient").on("input", restore_placeholder_in_firefox_for_no_input);
}

export function update_topic_inputbox_on_topics_policy_change(): void {
    if (!stream_data.can_use_empty_topic(compose_state.stream_id())) {
        const $input = $("input#stream_message_recipient_topic");
        $input.attr("placeholder", $t({defaultMessage: "Topic"}));
        $input.removeClass("empty-topic-display");
        const $topic_not_mandatory_placeholder = $("#topic-not-mandatory-placeholder");
        $topic_not_mandatory_placeholder.removeClass("visible");
        $topic_not_mandatory_placeholder.hide();
        return;
    }
    update_topic_displayed_text(compose_state.topic());
}

export function update_topic_displayed_text(topic_name = "", has_topic_focus = false): void {
    compose_state.topic(topic_name);

    const $input = $("input#stream_message_recipient_topic");
    const recipient_widget_hidden =
        $(".compose_select_recipient-dropdown-list-container").length === 0;
    const $topic_not_mandatory_placeholder = $("#topic-not-mandatory-placeholder");

    // reset
    $input.prop("disabled", false);
    $input.attr("placeholder", "");
    $input.removeClass("empty-topic-display empty-topic-only");
    $topic_not_mandatory_placeholder.removeClass("visible");
    $topic_not_mandatory_placeholder.hide();
    $("#compose_recipient_box").removeClass("disabled");

    if (!stream_data.can_use_empty_topic(compose_state.stream_id())) {
        $input.attr("placeholder", $t({defaultMessage: "Topic"}));
        // When topics are mandatory, no additional adjustments are needed.
        // Also, if the recipient in the compose box is not selected, the
        // placeholder will always be "Topic" and never "general chat".
        return;
    }

    // If `topics_policy` is set to `empty_topic_only`, disable the topic input
    // and empty the input box.
    if (stream_data.is_empty_topic_only_channel(compose_state.stream_id())) {
        compose_state.topic("");
        $input.prop("disabled", true);
        $input.addClass("empty-topic-only");
        $("#compose_recipient_box").addClass("disabled");
        $("textarea#compose-textarea").trigger("focus");
        has_topic_focus = false;
    }
    // Otherwise, we have some adjustments to make to display:
    // * a placeholder with the default topic name stylized
    // * the empty string topic stylized
    function update_placeholder_visibility(): void {
        $topic_not_mandatory_placeholder.toggleClass("visible", $input.val() === "");
    }

    const is_empty_string_topic = compose_state.topic() === "";
    if (
        is_empty_string_topic &&
        ($input.prop("disabled") || (!has_topic_focus && recipient_widget_hidden))
    ) {
        $input.attr("placeholder", util.get_final_topic_display_name(""));
        $input.addClass("empty-topic-display");
    } else {
        $topic_not_mandatory_placeholder.show();
        update_placeholder_visibility();
        $input.on("input", update_placeholder_visibility);
    }
}

export let update_compose_area_placeholder_text = (): void => {
    const $textarea: JQuery<HTMLTextAreaElement> = $("textarea#compose-textarea");
    // Change compose placeholder text only if compose box is open.
    if ($(".message_comp").css("display") === "none") {
        return;
    }
    const message_type = compose_state.get_message_type();

    let placeholder = compose_ui.DEFAULT_COMPOSE_PLACEHOLDER;
    if (message_type === "stream") {
        const stream_id = compose_state.stream_id();
        placeholder = compose_ui.compute_placeholder_text({
            message_type,
            stream_id,
            topic: compose_state.topic(),
        });
    } else if (message_type === "private") {
        placeholder = compose_ui.compute_placeholder_text({
            message_type,
            direct_message_user_ids: compose_pm_pill.get_user_ids(),
        });
    }

    $textarea.attr("placeholder", placeholder);
    compose_ui.autosize_textarea($textarea);
};

export function rewire_update_compose_area_placeholder_text(
    value: typeof update_compose_area_placeholder_text,
): void {
    update_compose_area_placeholder_text = value;
}

// This function addresses the issue of the placeholder not reappearing in Firefox
// when the user types into an input field and then deletes the content.
// The problem arises due to the `contenteditable` attribute, which in some browsers
// (like Firefox) inserts a <br> tag when the input is emptied. This <br> tag prevents
// the placeholder from showing up again. The function checks if the input is empty
// and contains a <br> tag, then removes it to restore the placeholder functionality.
export function restore_placeholder_in_firefox_for_no_input(): void {
    if ($("#private_message_recipient").text().trim() === "") {
        $("#private_message_recipient").empty();
    }
}
