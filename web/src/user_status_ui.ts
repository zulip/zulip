import $ from "jquery";
import type * as tippy from "tippy.js";

import render_set_status_overlay from "../templates/set_status_overlay.hbs";
import render_status_emoji_selector from "../templates/status_emoji_selector.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import * as emoji from "./emoji.ts";
import type {EmojiRenderingDetails} from "./emoji.ts";
import * as flatpickr from "./flatpickr.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as people from "./people.ts";
import * as timerender from "./timerender.ts";
import * as user_status from "./user_status.ts";
import type {TimeKey, UserStatusEmojiInfo} from "./user_status.ts";

let selected_emoji_info: Partial<UserStatusEmojiInfo> = {};
let default_status_messages_and_emoji_info: {
    status_text: string;
    emoji: EmojiRenderingDetails;
    expiry: TimeKey;
}[];
let scheduled_end_time_widget: dropdown_widget.DropdownWidget;
let scheduled_end_time: number | undefined;

type ScheduledEndTimeWidgetOption = {
    name: string;
    unique_id: string;
};

const scheduled_end_time_widget_options: ScheduledEndTimeWidgetOption[] = [
    {name: $t({defaultMessage: "Never"}), unique_id: "never"},
    {name: $t({defaultMessage: "In 30 minutes"}), unique_id: "in_thirty_minutes"},
    {name: $t({defaultMessage: "In one hour"}), unique_id: "in_one_hour"},
    {name: $t({defaultMessage: "Today at 5:00 PM"}), unique_id: "today_five_pm"},
    {name: $t({defaultMessage: "Tomorrow"}), unique_id: "tomorrow"},
    {name: $t({defaultMessage: "Custom"}), unique_id: "custom"},
];

const no_scheduled_end_time_set_message = $t({defaultMessage: "Keep status until you remove it."});

function select_scheduled_end_time(custom_time_selected?: number): void {
    const end_times = user_status.compute_scheduled_end_time(custom_time_selected);

    switch (scheduled_end_time_widget.current_value) {
        case "never":
            scheduled_end_time = end_times.never;
            break;
        case "in_thirty_minutes":
            scheduled_end_time = end_times.in_thirty_minutes;
            break;
        case "in_one_hour":
            scheduled_end_time = end_times.in_one_hour;
            break;
        case "today_five_pm":
            scheduled_end_time = end_times.today_five_pm;
            break;
        case "tomorrow":
            scheduled_end_time = end_times.tomorrow;
            break;
        case "custom":
            scheduled_end_time = end_times.custom;
            break;
    }
    const scheduled_timestamp = scheduled_end_time
        ? timerender.get_full_datetime(new Date(scheduled_end_time), "time")
        : no_scheduled_end_time_set_message;

    $("#scheduled_end_time").text(scheduled_timestamp);
    $("#scheduled_end_time").toggleClass("invisible", false);
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

    scheduled_end_time = undefined;

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

    const current_status_expire_time = user_status.get_scheduled_end_time();

    render_scheduled_end_time_widget();
    $("#scheduled_end_time").text(no_scheduled_end_time_set_message);

    if (current_status_expire_time !== undefined) {
        $("#scheduled_end_time_widget .dropdown_widget_value").text(
            $t(
                {defaultMessage: "{N}"},
                {
                    N: timerender.get_full_datetime(
                        new Date(current_status_expire_time * 1000),
                        "time",
                    ),
                },
            ),
        );
        $("#scheduled_end_time").toggleClass("invisible", true);
    }
}

export function submit_new_status(): void {
    const user_id = people.my_current_user_id();
    let old_status_text = user_status.get_status_text(user_id) ?? "";
    old_status_text = old_status_text.trim();
    const old_emoji_info = user_status.get_status_emoji(user_id);
    const new_status_text = input_field().val()?.trim() ?? "";
    const old_scheduled_end_time = user_status.get_scheduled_end_time();

    if (
        old_status_text === new_status_text &&
        !emoji_status_fields_changed(selected_emoji_info, old_emoji_info) &&
        old_scheduled_end_time === scheduled_end_time
    ) {
        dialog_widget.close();
        return;
    }

    if (scheduled_end_time !== undefined) {
        scheduled_end_time = Math.floor(scheduled_end_time / 1000);
    }

    user_status.server_update_status({
        status_text: new_status_text,
        emoji_name: selected_emoji_info.emoji_name ?? "",
        emoji_code: selected_emoji_info.emoji_code ?? "",
        reaction_type: selected_emoji_info.reaction_type ?? "",
        scheduled_end_time,
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
    const old_scheduled_end_time = user_status.get_scheduled_end_time();
    const $button = submit_button();

    if (
        (!new_status_text && !selected_emoji_info.emoji_name) ||
        (old_status_text === new_status_text &&
            !emoji_status_fields_changed(selected_emoji_info, old_emoji_info) &&
            old_scheduled_end_time === scheduled_end_time)
    ) {
        $button.prop("disabled", true);
    } else {
        $button.prop("disabled", false);

        if (scheduled_end_time === undefined) {
            scheduled_end_time_widget.render("never");
            select_scheduled_end_time();
        }
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
    return $("#set-user-status-modal").length > 0;
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

        const expires_in = default_status_messages_and_emoji_info.find(
            (default_status) => default_status.status_text === user_status_value,
        )!.expiry;
        scheduled_end_time_widget.render(expires_in);
        select_scheduled_end_time();
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
        toggle_clear_message_button();
    });

    $("#clear_status_message_button").on("click", () => {
        clear_message();
        set_selected_emoji_info({});
        update_button();
    });
}

function render_scheduled_end_time_widget(): void {
    const tippy_props: Partial<tippy.Props> = {
        placement: "bottom-start",
    };
    const opts: dropdown_widget.DropdownWidgetOptions = {
        widget_name: "scheduled_end_time",
        get_options: () => scheduled_end_time_widget_options,
        item_click_callback: scheduled_end_time_widget_callback,
        $events_container: $("#set-user-status-modal"),
        tippy_props,
        hide_search_box: true,
        default_id: "never",
        unique_id_type: "string",
    };
    scheduled_end_time_widget = new dropdown_widget.DropdownWidget(opts);
    scheduled_end_time_widget.setup();
}

function scheduled_end_time_widget_callback(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
): void {
    event.preventDefault();
    event.stopPropagation();
    if (scheduled_end_time_widget.current_value === "custom") {
        const now = new Date();
        now.setSeconds(0, 0);
        flatpickr.show_flatpickr(
            $(".dropdown-list-item-common-styles")[4]!,
            (datetime) => {
                const custom_time_selected = Date.parse(datetime);
                select_scheduled_end_time(custom_time_selected);
            },
            new Date(now).setHours(now.getHours() + 1),
            {
                minDate: now,
            },
        );
    }
    scheduled_end_time_widget.render();
    select_scheduled_end_time();
    update_button();
    dropdown.hide();
}

export function initialize(): void {
    default_status_messages_and_emoji_info = [
        {
            status_text: $t({defaultMessage: "Busy"}),
            emoji: emoji.get_emoji_details_by_name("working_on_it"),
            expiry: "in_one_hour",
        },
        {
            status_text: $t({defaultMessage: "In a meeting"}),
            emoji: emoji.get_emoji_details_by_name("calendar"),
            expiry: "in_one_hour",
        },
        {
            status_text: $t({defaultMessage: "Commuting"}),
            emoji: emoji.get_emoji_details_by_name("bus"),
            expiry: "in_thirty_minutes",
        },
        {
            status_text: $t({defaultMessage: "Out sick"}),
            emoji: emoji.get_emoji_details_by_name("hurt"),
            expiry: "tomorrow",
        },
        {
            status_text: $t({defaultMessage: "Vacationing"}),
            emoji: emoji.get_emoji_details_by_name("palm_tree"),
            expiry: "never",
        },
        {
            status_text: $t({defaultMessage: "Working remotely"}),
            emoji: emoji.get_emoji_details_by_name("house"),
            expiry: "today_five_pm",
        },
        {
            status_text: $t({defaultMessage: "At the office"}),
            emoji: emoji.get_emoji_details_by_name("office"),
            expiry: "today_five_pm",
        },
    ];
}
