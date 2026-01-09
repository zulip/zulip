import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_report_message_modal from "../templates/report_message_modal.hbs";

import * as channel from "./channel.ts";
import * as condense from "./condense.ts";
import * as dialog_widget from "./dialog_widget.ts";
import type {Option} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import {
    type MessageContainer,
    type MessageGroup,
    get_timestr,
    populate_group_from_message,
} from "./message_list_view.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import {update_elements} from "./rendered_markdown.ts";
import * as rows from "./rows.ts";
import {realm} from "./state_data.ts";
import {process_submessages} from "./submessage.ts";
import * as ui_report from "./ui_report.ts";
import {toggle_user_card_popover_for_message} from "./user_card_popover.ts";

function register_message_preview_click_handlers(
    $message_preview_container: JQuery,
    sender_id: number,
): void {
    // This function registers click handlers and mouseover effects
    // for the message sender in the message preview container.
    // The logic here is partly from message_list_hover.ts, and
    // partly from user_card_popover.ts.

    $message_preview_container.on("mouseover", ".sender_info_hover", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");
        $row.addClass("sender_info_hovered");
    });

    $message_preview_container.on("mouseout", ".sender_info_hover", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");
        $row.removeClass("sender_info_hovered");
    });

    $message_preview_container.on(
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
    const message_group = populate_group_from_message(message, false, false, undefined);
    if (message_group.is_stream) {
        message_group.user_can_resolve_topic = false;
        message_group.is_topic_editable = false;
    }
    return message_group;
}

function get_message_container_for_preview(message: Message): MessageContainer {
    const computed_variables = {
        include_sender: true,
        // Message report preview will be automatically collapsed
        is_hidden: false,
        msg: message,
        sender_is_bot: people.sender_is_bot(message),
        sender_is_deactivated: people.sender_is_deactivated(message),
        sender_is_guest: people.sender_is_guest(message),
        sender_color: people.get_by_user_id(message.sender_id)?.color ?? null,
        should_add_guest_indicator_for_sender: people.should_add_guest_user_indicator(
            message.sender_id,
        ),
        small_avatar_url: people.small_avatar_url(message),
        status_message: "",
        timestr: get_timestr(message),
        want_date_divider: false,
    };
    const unused_variables = {
        date_divider_html: undefined,
        edited: false,
        include_recipient: false,
        last_edit_timestamp: undefined,
        last_moved_timestamp: undefined,
        mention_classname: undefined,
        message_edit_notices_alongside_sender: false,
        message_edit_notices_for_status_message: false,
        message_edit_notices_in_left_col: false,
        modified: false,
        moved: false,
        year_changed: false,
    };
    return {
        ...computed_variables,
        ...unused_variables,
    };
}

function post_process_message_preview($row: JQuery): void {
    const $content = $row.find(".message_content");
    update_elements($content);
    const id = rows.id($row);
    process_submessages({
        $row,
        message_id: id,
    });
    // Disable most UI for interacting with message widget in the report
    // message preview UI.
    const $widget_content = $content.find(".widget-content");
    $widget_content.find("button, input, select").prop("disabled", true);
    $widget_content.find(".poll-edit-question, .poll-option-bar").hide();
}

export function show_message_report_modal(message: Message): void {
    const message_preview_body_args = get_message_container_for_preview(message);
    const html_body = render_report_message_modal({
        recipient_row_data: get_message_group_for_message_preview(message),
        message_container_data: {
            ...message_preview_body_args,
            message_list_id: "",
        },
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

        post_process_message_preview($report_message_preview_container.find(".message_row"));
        // Condense the message preview, the main motivation is to hide the
        // potentially unpleasant message content.
        $report_message_preview_container.find(".message_content").addClass("collapsed");
        condense.show_message_expander(
            $report_message_preview_container,
            null,
            $t({defaultMessage: "Show message"}),
        );

        $report_message_preview_container.on("click", ".message_expander", (e) => {
            const $content = $report_message_preview_container.find(".message_content");
            if ($content.hasClass("collapsed")) {
                $content.removeClass("collapsed");
                condense.show_message_condenser(
                    $report_message_preview_container,
                    null,
                    $t({defaultMessage: "Hide message"}),
                );
            }
            e.preventDefault();
            e.stopPropagation();
        });

        $report_message_preview_container.on("click", ".message_condenser", (e) => {
            const $content = $report_message_preview_container.find(".message_content");
            if (!$content.hasClass("collapsed")) {
                $content.addClass("collapsed");
                condense.show_message_expander(
                    $report_message_preview_container,
                    null,
                    $t({defaultMessage: "Show message"}),
                );
            }
            e.preventDefault();
            e.stopPropagation();
        });
        function get_message_report_types(): Option[] {
            return realm.server_report_message_types.map((report_type) => ({
                unique_id: report_type.key,
                name: report_type.name,
            }));
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
