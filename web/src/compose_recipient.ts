/* Compose box module responsible for the message's recipient */

import $ from "jquery";
import _, {isNumber} from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";

import * as compose_banner from "./compose_banner.ts";
import * as compose_fade from "./compose_fade.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import type {ComposeTriggeredOptions} from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import * as drafts from "./drafts.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {Option} from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_util from "./ui_util.ts";
import * as user_groups from "./user_groups.ts";
import * as util from "./util.ts";

type MessageType = "stream" | "private";
type DirectMessagesOption = {
    is_direct_message: boolean;
    unique_id: string | number;
    name: string;
};

function composing_to_current_topic_narrow(): boolean {
    return (
        util.lower_same(compose_state.stream_name(), narrow_state.stream_name() ?? "") &&
        util.lower_same(compose_state.topic(), narrow_state.topic() ?? "")
    );
}

function composing_to_current_private_message_narrow(): boolean {
    const compose_state_recipient = compose_state.private_message_recipient();
    const narrow_state_recipient = narrow_state.pm_emails_string();
    if (narrow_state_recipient === undefined) {
        return false;
    }
    return (
        Boolean(compose_state_recipient) &&
        Boolean(narrow_state_recipient) &&
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
        const recipients = compose_state.private_message_recipient();
        if (
            recipients &&
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
    drafts.update_compose_draft_count();
    check_posting_policy_for_compose_box();
}

export function get_posting_policy_error_message(): string {
    if (compose_state.selected_recipient_id === "direct") {
        const recipients = compose_pm_pill.get_user_ids_string();
        return compose_validate.check_dm_permissions_and_get_error_string(recipients);
    }

    if (!isNumber(compose_state.selected_recipient_id)) {
        return "";
    }

    const stream = sub_store.get(compose_state.selected_recipient_id);
    if (stream && !stream_data.can_post_messages_in_stream(stream)) {
        return $t({
            defaultMessage: "You do not have permission to post in this channel.",
        });
    }
    return "";
}

export let check_posting_policy_for_compose_box = (): void => {
    const banner_text = get_posting_policy_error_message();
    if (banner_text === "") {
        compose_validate.set_recipient_disallowed(false);
        compose_banner.clear_errors();
        return;
    }

    let banner_classname = compose_banner.CLASSNAMES.no_post_permissions;
    compose_validate.set_recipient_disallowed(true);
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
        private_message_recipient: compose_state.private_message_recipient(),
    };
    update_compose_for_message_type(opts);
    update_placeholder_text();
    compose_ui.set_focus(opts);
}

function update_recipient_label(stream_id?: number): void {
    const stream = stream_id !== undefined ? stream_data.get_sub_by_id(stream_id) : undefined;
    if (stream === undefined) {
        $("#compose_select_recipient_widget .dropdown_widget_value").text(
            $t({defaultMessage: "Select a channel"}),
        );
    } else {
        $("#compose_select_recipient_widget .dropdown_widget_value").html(
            render_inline_decorated_stream_name({stream, show_colored_icon: true}),
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
            `<i class="zulip-icon zulip-icon-users stream-privacy-type-icon"></i> ${direct_message_label}`,
        );
    }
    compose_banner.clear_errors();
    compose_banner.clear_warnings();
    compose_banner.clear_uploads();
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
    on_compose_select_recipient_update();
    dropdown.hide();
    event.preventDefault();
    event.stopPropagation();
}

function get_options_for_recipient_widget(): Option[] {
    const options: (Option | DirectMessagesOption)[] =
        stream_data.get_options_for_dropdown_widget();

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

// NOTE: Since tippy triggers this on `mousedown` it is always triggered before say a `click` on `textarea`.
function on_hidden_callback(): void {
    if (compose_state.get_message_type() === "stream") {
        // Always move focus to the topic input even if it's not empty,
        // since it's likely the user will want to update the topic
        // after updating the stream.
        ui_util.place_caret_at_end(util.the($("input#stream_message_recipient_topic")));
    } else {
        if (compose_state.private_message_recipient().length === 0) {
            $("#private_message_recipient").trigger("focus").trigger("select");
        } else {
            $("textarea#compose-textarea").trigger("focus");
        }
    }
}

export function handle_middle_pane_transition(): void {
    if (compose_state.composing()) {
        update_narrow_to_recipient_visibility();
    }
}

export function initialize(): void {
    new dropdown_widget.DropdownWidget({
        widget_name: "compose_select_recipient",
        get_options: get_options_for_recipient_widget,
        item_click_callback,
        $events_container: $("body"),
        on_exit_with_escape_callback: focus_compose_recipient,
        // We want to focus on topic box if dropdown was closed via selecting an item.
        focus_target_on_hidden: false,
        on_hidden_callback,
        dropdown_input_visible_selector: "#compose_select_recipient_widget_wrapper",
        prefer_top_start_placement: true,
        tippy_props: {
            offset: [-10, 5],
        },
    }).setup();

    // `input` isn't relevant for streams since it registers as a change only
    // when an item in the dropdown is selected.
    $("#stream_message_recipient_topic,#private_message_recipient").on(
        "input",
        update_on_recipient_change,
    );
    // changes for the stream dropdown are handled in on_compose_select_recipient_update
    $("#stream_message_recipient_topic,#private_message_recipient").on("change", () => {
        update_on_recipient_change();
        compose_state.set_recipient_edited_manually(true);
    });
}

export let update_placeholder_text = (): void => {
    const $textarea: JQuery<HTMLTextAreaElement> = $("textarea#compose-textarea");
    // Change compose placeholder text only if compose box is open.
    if (!$textarea.is(":visible")) {
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

export function rewire_update_placeholder_text(value: typeof update_placeholder_text): void {
    update_placeholder_text = value;
}
