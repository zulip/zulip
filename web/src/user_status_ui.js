import $ from "jquery";

import render_set_status_overlay from "../templates/set_status_overlay.hbs";
import render_status_emoji_selector from "../templates/status_emoji_selector.hbs";

import * as dialog_widget from "./dialog_widget";
import * as emoji from "./emoji";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as people from "./people";
import * as user_status from "./user_status";

let selected_emoji_info = {};
let default_status_messages_and_emoji_info;

export function set_selected_emoji_info(emoji_info) {
    selected_emoji_info = {...emoji_info};
    rebuild_status_emoji_selector_ui(selected_emoji_info);
}
export function input_field() {
    return $("#set-user-status-modal input.user-status");
}

export function submit_button() {
    return $("#set-user-status-modal .dialog_submit_button");
}

export function open_user_status_modal() {
    const user_id = people.my_current_user_id();
    const selected_emoji_info = user_status.get_status_emoji(user_id) || {};
    const rendered_set_status_overlay = render_set_status_overlay({
        default_status_messages_and_emoji_info,
        selected_emoji_info,
    });

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Set status"}),
        html_body: rendered_set_status_overlay,
        html_submit_button: $t_html({defaultMessage: "Save"}),
        id: "set-user-status-modal",
        on_click: submit_new_status,
        post_render: user_status_post_render,
        on_shown() {
            input_field().trigger("focus");
        },
    });
}

export function submit_new_status() {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) || "";
    old_status_text = old_status_text.trim();
    const old_emoji_info = user_status.get_status_emoji(user_id) || {};
    const new_status_text = input_field().val().trim();

    if (
        old_status_text === new_status_text &&
        old_emoji_info.emoji_name === selected_emoji_info.emoji_name &&
        old_emoji_info.reaction_type === selected_emoji_info.reaction_type &&
        old_emoji_info.emoji_code === selected_emoji_info.emoji_code
    ) {
        dialog_widget.close_modal();
        return;
    }

    user_status.server_update_status({
        status_text: new_status_text,
        emoji_name: selected_emoji_info.emoji_name || "",
        emoji_code: selected_emoji_info.emoji_code || "",
        reaction_type: selected_emoji_info.reaction_type || "",
        success() {
            dialog_widget.close_modal();
        },
    });
}

export function update_button() {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) || "";
    old_status_text = old_status_text.trim();
    const old_emoji_info = user_status.get_status_emoji(user_id) || {};
    const new_status_text = input_field().val().trim();
    const $button = submit_button();

    if (
        old_status_text === new_status_text &&
        old_emoji_info.emoji_name === selected_emoji_info.emoji_name &&
        old_emoji_info.reaction_type === selected_emoji_info.reaction_type &&
        old_emoji_info.emoji_code === selected_emoji_info.emoji_code
    ) {
        $button.prop("disabled", true);
    } else {
        $button.prop("disabled", false);
    }
}

export function toggle_clear_message_button() {
    if (input_field().val() !== "" || selected_emoji_info.emoji_name) {
        $("#clear_status_message_button").prop("disabled", false);
    } else {
        $("#clear_status_message_button").prop("disabled", true);
    }
}

export function clear_message() {
    const $field = input_field();
    $field.val("");
    $("#clear_status_message_button").prop("disabled", true);
}

export function user_status_picker_open() {
    return $("#set-user-status-modal").length !== 0;
}

function rebuild_status_emoji_selector_ui(selected_emoji_info) {
    let selected_emoji = null;
    if (selected_emoji_info && Object.keys(selected_emoji_info).length) {
        selected_emoji = selected_emoji_info;
    }
    const rendered_status_emoji_selector = render_status_emoji_selector({selected_emoji});
    $("#set-user-status-modal .status-emoji-wrapper").html(rendered_status_emoji_selector);
}

function user_status_post_render() {
    const user_id = people.my_current_user_id();
    const old_status_text = user_status.get_status_text(user_id);
    const old_emoji_info = user_status.get_status_emoji(user_id) || {};
    set_selected_emoji_info(old_emoji_info);
    const $field = input_field();
    $field.val(old_status_text);
    toggle_clear_message_button();

    const $button = submit_button();
    $button.prop("disabled", true);

    $("#set-user-status-modal .user-status-value").on("click", (event) => {
        event.stopPropagation();
        const user_status_value = $(event.currentTarget).text().trim();
        $("input.user-status").val(user_status_value);

        const emoji_info = default_status_messages_and_emoji_info.find(
            (status) => status.status_text === user_status_value,
        ).emoji;
        set_selected_emoji_info(emoji_info);
        toggle_clear_message_button();
        update_button();
    });

    input_field().on("keypress", (event) => {
        if (keydown_util.is_enter_event(event)) {
            event.preventDefault();

            submit_new_status();
        }
    });

    input_field().on("keyup", () => {
        update_button();
        toggle_clear_message_button();
    });

    $("#clear_status_message_button").on("click", () => {
        clear_message();
        set_selected_emoji_info();
        update_button();
    });
}

export function initialize() {
    default_status_messages_and_emoji_info = [
        {
            status_text: $t({defaultMessage: "Busy"}),
            emoji: emoji.get_emoji_details_by_name("working_on_it"),
        },
        {
            status_text: $t({defaultMessage: "In a meeting"}),
            emoji: emoji.get_emoji_details_by_name("calendar"),
        },
        {
            status_text: $t({defaultMessage: "Commuting"}),
            emoji: emoji.get_emoji_details_by_name("bus"),
        },
        {
            status_text: $t({defaultMessage: "Out sick"}),
            emoji: emoji.get_emoji_details_by_name("hurt"),
        },
        {
            status_text: $t({defaultMessage: "Vacationing"}),
            emoji: emoji.get_emoji_details_by_name("palm_tree"),
        },
        {
            status_text: $t({defaultMessage: "Working remotely"}),
            emoji: emoji.get_emoji_details_by_name("house"),
        },
        {
            status_text: $t({defaultMessage: "At the office"}),
            emoji: emoji.get_emoji_details_by_name("office"),
        },
    ];
}
