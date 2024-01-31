import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_set_status_overlay from "../templates/set_status_overlay.hbs";
import render_status_emoji_selector from "../templates/status_emoji_selector.hbs";

import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import * as emoji from "./emoji";
import type {EmojiRenderingDetails} from "./emoji";
import * as flatpickr from "./flatpickr";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as people from "./people";
import * as timerender from "./timerender";
import * as user_status from "./user_status";
import type {UserStatusEmojiInfo} from "./user_status";

let selected_emoji_info: Partial<UserStatusEmojiInfo> = {};
let default_status_messages_and_emoji_info: {status_text: string; emoji: EmojiRenderingDetails}[];
let user_status_widget: dropdown_widget.DropdownWidget;
let is_custom_time_selected: boolean;
let status_end_time: number | undefined;
let scheduled_timestamp: string;
let custom_time_selected: number;

type ClearExpiredStatusOption = {
    name: string;
    unique_id: number;
};

type UserStatusData = {
    status_text: string;
    emoji_name: string;
    emoji_code: string;
    reaction_type: string;
};

const clear_expired_status_option_vals: ClearExpiredStatusOption[] = [
    {name: $t({defaultMessage: "Never"}), unique_id: 1},
    {name: $t({defaultMessage: "In one hour"}), unique_id: 2},
    {name: $t({defaultMessage: "Today at 5:00 PM"}), unique_id: 3},
    {name: $t({defaultMessage: "Tomorrow at 9:00 AM"}), unique_id: 4},
    {name: $t({defaultMessage: "Custom"}), unique_id: 5},
];

function compute_status_end_time(now = new Date()): void {
    const today = new Date(now);
    const tomorrow = new Date(new Date(now).setDate(now.getDate() + 1));

    // today at 5pm
    const today_at_five_pm = Math.floor(today.setHours(17, 0, 0, 0) / 1000);
    // today 1 hour later
    const one_hour_later = Math.floor((now.getTime() + 60 * 60 * 1000) / 1000);
    // tomorrow at 9am
    const tomorrow_nine_am = Math.floor(tomorrow.setHours(9, 0, 0, 0) / 1000);
    // custom time
    const custom_time = custom_time_selected;
    switch (user_status_widget.current_value) {
        case 1:
            status_end_time = undefined;
            break;
        case 2:
            status_end_time = one_hour_later;
            break;
        case 3:
            status_end_time = today_at_five_pm;
            break;
        case 4:
            status_end_time = tomorrow_nine_am;
            break;
        case 5:
            status_end_time = custom_time;
            break;
    }
    scheduled_timestamp = status_end_time
        ? timerender.get_full_datetime(new Date(status_end_time * 1000), "time")
        : "";
}

export function set_selected_emoji_info(emoji_info: Partial<UserStatusEmojiInfo>): void {
    selected_emoji_info = {...emoji_info};
    rebuild_status_emoji_selector_ui(selected_emoji_info);
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

    status_end_time = undefined;

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

    render_clear_expired_status_widget();
    if (user_status.get_user_status_end_time()) {
        $("#clear_expired_user_status_widget .dropdown_widget_value").text(
            $t(
                {defaultMessage: "{N}"},
                {
                    N: timerender.get_full_datetime(
                        new Date(user_status.get_user_status_end_time() * 1000),
                        "time",
                    ),
                },
            ),
        );
    }
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
    const data: UserStatusData = {
        status_text: new_status_text,
        emoji_name: selected_emoji_info.emoji_name ?? "",
        emoji_code: selected_emoji_info.emoji_code ?? "",
        reaction_type: selected_emoji_info.reaction_type ?? "",
    };

    if (status_end_time !== undefined) {
        user_status.server_update_status({
            ...data,
            status_end_time,
            success() {
                dialog_widget.close();
            },
        });
        return;
    }

    user_status.server_update_status({
        ...data,
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
        (!new_status_text && !selected_emoji_info.emoji_name) ||
        (old_status_text === new_status_text &&
            !emoji_status_fields_changed(selected_emoji_info, old_emoji_info))
    ) {
        $button.prop("disabled", true);
    } else {
        $button.prop("disabled", false);
    }
}

export function toggle_clear_message_button(): void {
    if (input_field().val() !== "" || selected_emoji_info.emoji_name) {
        $("#clear_status_message_button").prop("disabled", false);
    } else {
        $("#clear_status_message_button").prop("disabled", true);
    }
}

export function clear_message(): void {
    const $field = input_field();
    $field.val("");
    $("#clear_status_message_button").prop("disabled", true);
}

export function user_status_picker_open(): boolean {
    return $("#set-user-status-modal").length !== 0;
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
        old_emoji_info.emoji_code === selected_emoji_info.emoji_code &&
        user_status.get_user_status_end_time() === status_end_time
    ) {
        return false;
    }

    return true;
}

function rebuild_status_emoji_selector_ui(selected_emoji_info: Partial<UserStatusEmojiInfo>): void {
    let selected_emoji = null;
    if (selected_emoji_info && Object.keys(selected_emoji_info).length) {
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
    toggle_clear_message_button();

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
        set_selected_emoji_info({});
        update_button();
    });
}

function render_clear_expired_status_widget(): void {
    const tippy_props: Partial<tippy.Props> = {
        placement: "bottom-start",
    };
    const opts = {
        widget_name: "clear_expired_user_status",
        get_options: clear_expired_status_options,
        item_click_callback: clear_expired_status_item_callback,
        $events_container: $("#set-user-status-modal"),
        tippy_props,
        hide_search_box: true,
        default_id: 1,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
    };
    user_status_widget = new dropdown_widget.DropdownWidget(opts);
    user_status_widget.setup();
}

export function clear_expired_status_options(): ClearExpiredStatusOption[] {
    return clear_expired_status_option_vals;
}

function clear_expired_status_item_callback(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
): void {
    event.preventDefault();
    event.stopPropagation();
    if (user_status_widget.current_value === 5) {
        is_custom_time_selected = false;
        const current_time = new Date();
        flatpickr.show_flatpickr(
            $(".dropdown-list-item-common-styles")[4],
            compute_custom_time_selected,
            new Date(current_time.getTime() + 60 * 60 * 1000),
            {
                minDate: new Date(current_time.getTime()),
                onClose() {
                    // Return to normal state.
                    user_status_widget.render();
                    dropdown.hide();
                    if (!is_custom_time_selected) {
                        $("#dropdown-option-chosen").text($t({defaultMessage: "Time not chosen"}));
                    }
                },
            },
        );
    } else {
        user_status_widget.render();
        compute_status_end_time();
        dropdown.hide();
        $("#dropdown-option-chosen").text(scheduled_timestamp);
    }
    update_button();
}

function compute_custom_time_selected(time: number | string): void {
    is_custom_time_selected = true;
    if (!Number.isInteger(time)) {
        assert(typeof time === "string");
        time = Math.floor(Date.parse(time) / 1000);
    }
    assert(typeof time === "number");
    custom_time_selected = time;
    compute_status_end_time();
    $("#dropdown-option-chosen").text(scheduled_timestamp);
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
