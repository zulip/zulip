import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_inline_stream_or_topic_reference from "../templates/inline_stream_or_topic_reference.hbs";
import render_report_message_modal from "../templates/report_message_modal.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import type {Option} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t_html} from "./i18n.ts";
import type {Message} from "./message_store.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import * as util from "./util.ts";

export const message_report_type_values = {
    spam: {
        unique_id: "spam",
        description: $t_html({defaultMessage: "Spam"}),
    },
    harassment: {
        unique_id: "harassment",
        description: $t_html({defaultMessage: "Harassment"}),
    },
    inappropriate: {
        unique_id: "inappropriate",
        description: $t_html({defaultMessage: "Inappropriate"}),
    },
    norms: {
        unique_id: "norms",
        description: $t_html({defaultMessage: "Norms"}),
    },
};

export function show_message_report_modal(message: Message): void {
    const html_body = render_report_message_modal({});
    let report_type_dropdown_widget: dropdown_widget.DropdownWidget;

    function message_report_post_render(): void {
        function get_message_report_types(): Option[] {
            // Keep this in sync with zerver/models/realms/Realm.REPORT_MESSAGE_REASONS
            const options: Option[] = [
                ...Object.entries(message_report_type_values)
                    .map(([option_name, option_data]) => ({
                        unique_id: option_name,
                        name: option_data.description,
                    }))
                    .toSorted(),
                {
                    unique_id: "other",
                    name: $t_html({defaultMessage: "Other"}),
                },
            ];
            return options;
        }

        function message_report_type_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {
            report_type_dropdown_widget.render();
            $(".report-type-wrapper").trigger("input");

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
        const report_description = $<HTMLInputElement>("#message-report-description").val()!.trim();
        if (selected_report_type === "other" && !report_description) {
            ui_report.error(
                $t_html({defaultMessage: "Please provide an explanation"}),
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

    function get_modal_heading_html(message: Message): string {
        switch (message.type) {
            case "stream": {
                const topic_display_name = util.get_final_topic_display_name(message.topic);
                const is_empty_string_topic = message.topic === "";
                const stream = sub_store.get(message.stream_id);
                assert(stream !== undefined);

                return $t_html(
                    {
                        defaultMessage:
                            "Report a message sent by <z-message-sender></z-message-sender> in <z-stream-or-topic></z-stream-or-topic>",
                    },
                    {
                        "z-stream-or-topic": () =>
                            render_inline_stream_or_topic_reference({
                                topic_display_name,
                                is_empty_string_topic,
                                stream,
                                show_colored_icon: true,
                            }),
                        "z-message-sender": () => message.sender_full_name,
                    },
                );
            }
            case "private":
                return $t_html(
                    {
                        defaultMessage:
                            "Report a private message sent by <z-message-sender></z-message-sender>",
                    },
                    {
                        "z-message-sender": () => message.sender_full_name,
                    },
                );
            default:
                return $t_html({
                    defaultMessage: "Report a private message",
                });
        }
    }

    dialog_widget.launch({
        html_heading: get_modal_heading_html(message),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Submit"}),
        help_link: "/help/delete-a-message#delete-a-message-completely",
        id: "message_report_modal",
        form_id: "message_report_form",
        on_click: report_message,
        post_render: message_report_post_render,
        loading_spinner: true,
    });
}
