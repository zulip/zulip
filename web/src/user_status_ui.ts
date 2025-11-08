import $ from "jquery";

import render_set_status_overlay from "../templates/set_status_overlay.hbs";
import render_status_emoji_selector from "../templates/status_emoji_selector.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import * as emoji from "./emoji.ts";
import type {EmojiRenderingDetails} from "./emoji.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as people from "./people.ts";
import * as user_status from "./user_status.ts";
import type {UserStatusEmojiInfo} from "./user_status.ts";

let selected_emoji_info: Partial<UserStatusEmojiInfo> = {};
let default_status_messages_and_emoji_info: {status_text: string; emoji: EmojiRenderingDetails}[];

export function set_selected_emoji_info(emoji_info: Partial<UserStatusEmojiInfo>): void {
    selected_emoji_info = {...emoji_info};
    rebuild_status_emoji_selector_ui(selected_emoji_info);
    toggle_clear_status_button();
}
export function input_field(): JQuery<HTMLInputElement> {
    return $<HTMLInputElement>("#set-user-status-modal input.user-status");
}

export function submit_button(): JQuery {
    return $("#set-user-status-modal .dialog_submit_button");
}

export function open_user_status_modal(): void {
    const user_id = people.my_current_user_id();
    const selected_emoji_info = user_status.get_status_emoji(user_id) ?? {};
    const rendered_set_status_overlay = render_set_status_overlay({
        default_status_messages_and_emoji_info,
        selected_emoji_info,
    });

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Set status"}),
        html_body: rendered_set_status_overlay,
        html_submit_button: $t_html({defaultMessage: "Save"}),
        id: "set-user-status-modal",
        loading_spinner: true,
        on_click: submit_new_status,
        post_render: user_status_post_render,
        on_shown() {
            input_field().trigger("focus");
        },
    });
}

export function submit_new_status(): void {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) ?? "";
    old_status_text = old_status_text.trim();
    const old_emoji_info = user_status.get_status_emoji(user_id);
    const new_status_text = input_field().val()?.trim() ?? "";

    if (
        old_status_text === new_status_text &&
        !emoji_status_fields_changed(selected_emoji_info, old_emoji_info)
    ) {
        dialog_widget.close();
        return;
    }

    user_status.server_update_status({
        status_text: new_status_text,
        emoji_name: selected_emoji_info.emoji_name ?? "",
        emoji_code: selected_emoji_info.emoji_code ?? "",
        reaction_type: selected_emoji_info.reaction_type ?? "",
        success() {
            dialog_widget.close();
        },
    });
}

export function update_button(): void {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) ?? "";
    old_status_text = old_status_text.trim();
    const old_emoji_info = user_status.get_status_emoji(user_id);
    const new_status_text = input_field().val()?.trim() ?? "";
    const $button = submit_button();

    if (
        old_status_text === new_status_text &&
        !emoji_status_fields_changed(selected_emoji_info, old_emoji_info)
    ) {
        $button.prop("disabled", true);
    } else {
        $button.prop("disabled", false);
    }
}

export function clear_message(): void {
    const $field = input_field();
    $field.val("");
    toggle_clear_status_button();
}

export function user_status_picker_open(): boolean {
    return $("#set-user-status-modal").length > 0;
}

export function toggle_clear_status_button(): void {
    if (input_field().val() === "" && !selected_emoji_info.emoji_name) {
        $("#clear_status_message_button").hide();
    } else {
        $("#clear_status_message_button").show();
    }
}

function emoji_status_fields_changed(
    selected_emoji_info: Partial<UserStatusEmojiInfo>,
    old_emoji_info?: UserStatusEmojiInfo,
): boolean {
    if (old_emoji_info === undefined && Object.keys(selected_emoji_info).length === 0) {
        return false;
    } else if (
        old_emoji_info !== undefined &&
        old_emoji_info.emoji_name === selected_emoji_info.emoji_name &&
        old_emoji_info.reaction_type === selected_emoji_info.reaction_type &&
        old_emoji_info.emoji_code === selected_emoji_info.emoji_code
    ) {
        return false;
    }

    return true;
}

function rebuild_status_emoji_selector_ui(selected_emoji_info: Partial<UserStatusEmojiInfo>): void {
    let selected_emoji = null;
    if (selected_emoji_info && Object.keys(selected_emoji_info).length > 0) {
        selected_emoji = selected_emoji_info;
    }
    const rendered_status_emoji_selector = render_status_emoji_selector({selected_emoji});
    $("#set-user-status-modal .status-emoji-wrapper").html(rendered_status_emoji_selector);
}

function user_status_post_render(): void {
    const user_id = people.my_current_user_id();
    const old_status_text = user_status.get_status_text(user_id) ?? "";
    const old_emoji_info = user_status.get_status_emoji(user_id) ?? {};
    set_selected_emoji_info(old_emoji_info);
    const $field = input_field();
    $field.val(old_status_text);
    toggle_clear_status_button();

    const $button = submit_button();
    $button.prop("disabled", true);

    $("#set-user-status-modal .user-status-value").on("click", (event) => {
        event.stopPropagation();
        const user_status_value = $(event.currentTarget).text().trim();
        $("input.user-status").val(user_status_value);

        const emoji_info =
            default_status_messages_and_emoji_info.find(
                (status) => status.status_text === user_status_value,
            )?.emoji ?? {};
        set_selected_emoji_info(emoji_info);
        toggle_clear_status_button();
        update_button();
    });

    input_field().on("keydown", (event) => {
        if (keydown_util.is_enter_event(event)) {
            event.preventDefault();

            submit_new_status();
        }
    });

    input_field().on("keyup", () => {
        update_button();
        toggle_clear_status_button();
    });

    $("#clear_status_message_button").on("click", () => {
        clear_message();
        set_selected_emoji_info({});
        update_button();
    });
}

export function initialize(): void {
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
