import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_report_message_modal from "../templates/report_message_modal.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import type {Option} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t_html} from "./i18n.ts";
import {type MessageGroup, get_timestr, populate_group_from_message} from "./message_list_view.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import * as ui_report from "./ui_report.ts";
import {toggle_user_card_popover_for_message} from "./user_card_popover.ts";

export const message_report_type_options: Option[] = [
    {
        unique_id: "spam",
        name: $t_html({defaultMessage: "Spam"}),
    },
    {
        unique_id: "harassment",
        name: $t_html({defaultMessage: "Harassment"}),
    },
    {
        unique_id: "inappropriate",
        name: $t_html({defaultMessage: "Inappropriate"}),
    },
    {
        unique_id: "norms",
        name: $t_html({defaultMessage: "Violates community norms"}),
    },
];

type MessagePreviewRenderContext = {
    include_sender: boolean;
    msg: Message;
    sender_is_bot: boolean;
    should_add_guest_indicator_for_sender: boolean;
    small_avatar_url: string;
    timestr: string;
    message_list_id: string;
    status_message: boolean;
    want_date_divider: boolean;
    hide_message_reactions: boolean;
    hide_message_controls: boolean;
};

function register_message_preview_click_handlers(
    message_preview_container: JQuery,
    sender_id: number,
): void {
    // This function registers click handlers and mouseover effects
    // for the message sender in the message preview container.
    // The logic here is partly from message_list_hover.ts, and
    // partly from user_card_popover.ts.

    message_preview_container.on("mouseover", ".sender_info_hover", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");
        $row.addClass("sender_info_hovered");
    });

    message_preview_container.on("mouseout", ".sender_info_hover", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");
        $row.removeClass("sender_info_hovered");
    });

    message_preview_container.on(
        "click",
        ".sender_name, .inline-profile-picture-wrapper",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            const user = people.get_by_user_id(sender_id);
            toggle_user_card_popover_for_message(this, user, sender_id, true);
        },
    );
}

function get_message_group_for_message_preview(message: Message): MessageGroup {
    // This creates a simpler recipient_row without element like the
    // topic menu and topic visibility policy menu.
    const message_group = populate_group_from_message(message, false, false, undefined, true, true);
    if (message_group.is_stream) {
        message_group.user_can_resolve_topic = false;
        message_group.is_topic_editable = false;
    }
    return message_group;
}

function get_message_preview_body_args(message: Message): MessagePreviewRenderContext {
    // This creates a simpler message body without elements like the
    // message actions and reactions.
    const include_sender = true;
    const sender_is_bot = people.sender_is_bot(message);
    const should_add_guest_indicator_for_sender = people.should_add_guest_user_indicator(
        message.sender_id,
    );
    const small_avatar_url = people.small_avatar_url(message);
    const timestr = get_timestr(message);
    return {
        include_sender,
        msg: message,
        sender_is_bot,
        should_add_guest_indicator_for_sender,
        small_avatar_url,
        timestr,
        message_list_id: "",
        status_message: false,
        want_date_divider: false,
        hide_message_reactions: true,
        hide_message_controls: true,
    };
}

export function show_message_report_modal(message: Message): void {
    const message_preview_recipient_row_args = get_message_group_for_message_preview(message);
    const message_preview_body_args = get_message_preview_body_args(message);
    const html_body = render_report_message_modal({
        ...message_preview_recipient_row_args,
        ...message_preview_body_args,
    });
    let report_type_dropdown_widget: dropdown_widget.DropdownWidget;
    let $message_report_description: JQuery<HTMLTextAreaElement>;

    function message_report_post_render(): void {
        $message_report_description = $<HTMLTextAreaElement>("textarea#message-report-description");
        const $report_message_preview_container = $("#report-message-preview-container");

        function check_toggle_submit_button(): void {
            const selected_report_type = report_type_dropdown_widget.value();
            assert(selected_report_type !== undefined);
            const report_description = $message_report_description.val();
            const $submit_button = $(".dialog_submit_button");
            $submit_button.prop(
                "disabled",
                selected_report_type === "other" && !report_description,
            );
        }

        register_message_preview_click_handlers(
            $report_message_preview_container,
            message.sender_id,
        );

        function get_message_report_types(): Option[] {
            // Keep this in sync with zerver/models/realms/Realm.REPORT_MESSAGE_REASONS
            return [
                ...message_report_type_options,
                {
                    unique_id: "other",
                    name: $t_html({defaultMessage: "Other reason"}),
                },
            ];
        }

        $message_report_description.on("input", check_toggle_submit_button);

        function message_report_type_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {
            report_type_dropdown_widget.render();
            $(".report-type-wrapper").trigger("input");
            check_toggle_submit_button();
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
        }

        report_type_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: "report_type_options",
            get_options: get_message_report_types,
            item_click_callback: message_report_type_click_callback,
            $events_container: $("#message_report_modal"),
            default_id: "spam",
            unique_id_type: "string",
        });
        report_type_dropdown_widget.setup();
        report_type_dropdown_widget.render();
    }

    function report_message(): void {
        const selected_report_type = report_type_dropdown_widget.value();
        assert(selected_report_type !== undefined);
        const report_description = $<HTMLTextAreaElement>("textarea#message-report-description")
            .val()!
            .trim();
        if (selected_report_type === "other" && !report_description) {
            ui_report.error(
                $t_html({defaultMessage: "Please explain why you are reporting this message."}),
                undefined,
                $("#dialog_error"),
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }

        const data = {
            report_type: selected_report_type.toString(),
            description: report_description,
        };
        const url = "/json/messages/" + encodeURIComponent(message.id) + "/report";

        void channel.post({
            url,
            data,
            cache: false,
            success() {
                dialog_widget.close();
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                dialog_widget.hide_dialog_spinner();
            },
        });
    }

    dialog_widget.launch({
        html_heading: $t_html({
            defaultMessage: "Report a message",
        }),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Submit"}),
        help_link: "/help/report-a-message",
        id: "message_report_modal",
        form_id: "message_report_form",
        on_click: report_message,
        post_render: message_report_post_render,
        loading_spinner: true,
    });
}
