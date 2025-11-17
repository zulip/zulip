import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_report_message_modal from "../templates/report_message_modal.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import type {Option} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t_html} from "./i18n.ts";
import type {Message} from "./message_store.ts";
import {realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";

export function show_message_report_modal(message: Message): void {
    const html_body = render_report_message_modal({});
    let report_type_dropdown_widget: dropdown_widget.DropdownWidget;
    let $message_report_description: JQuery<HTMLTextAreaElement>;

    function message_report_post_render(): void {
        $message_report_description = $<HTMLTextAreaElement>("textarea#message-report-description");

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
