import $ from "jquery";
import _ from "lodash";
import type * as tippy from "tippy.js";

import render_report_message_modal from "../templates/report_message_modal.hbs";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
import type {Message} from "./message_store.ts";
import type {Option} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";

export async function show_message_report_modal(message?: Message): Promise<void> {
    const html_body = render_report_message_modal({});

    function message_report_post_render(): void {
        function get_message_report_types(): Option[] {
            // Keep this in sync with zerver/models/realms/Realm.REPORT_MESSAGE_REASONS
            const options: Option[] = [
                {
                    name: $t_html({defaultMessage: "Spam"}),
                    unique_id: "spam",
                },
                {
                    name: $t_html({defaultMessage: "Harassment"}),
                    unique_id: "harassment",
                },
                {
                    name: $t_html({defaultMessage: "Inappropriate"}),
                    unique_id: "inappropriate",
                },
                {
                    name: $t_html({defaultMessage: "Norms"}),
                    unique_id: "norms",
                },
                {
                    name: $t_html({defaultMessage: "Other"}),
                    unique_id: "other",
                },
            ];
            console.log(options);
            return options;
        }

        function message_report_type_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {}

        let report_type_dropdown_widget = new dropdown_widget.DropdownWidget({
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

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Report a message"}),
        html_body: html_body,
        html_submit_button: $t_html({defaultMessage: "Submit"}),
        help_link: "/help/delete-a-message#delete-a-message-completely",
        id: "message_report_modal",
        form_id: "message_report_form",
        on_click() {
            return;
        },
        post_render: message_report_post_render,
        loading_spinner: true,
    });
}
