import $ from "jquery";
import assert from "minimalistic-assert";

import render_confirm_multiple_message_delete from "../templates/confirm_dialog/confirm_multiple_message_delete.hbs";

import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
import * as message_delete from "./message_delete.ts";
import * as message_lists from "./message_lists.ts";
import {show_multiple_messages_delete_banner} from "./navbar_alerts.ts";
import * as ui_report from "./ui_report.ts";

export function initiate_multiple_message_selection(starting_message_id: number): void {
    compose_actions.cancel();
    show_multiple_messages_delete_banner();
    const $rows = message_lists.all_current_message_rows();

    $rows.each(function () {
        const $row = $(this);
        $row.find(".message_controls").remove();
        $row.find(".message_reactions").remove();

        const $select_el = $row.find(".multiple_messages_select");
        $select_el.show();

        const $checkbox = $select_el.find("input");
        const message_id = Number($checkbox.attr("data-message-id"));

        const message = message_lists.current?.get(message_id);
        assert(message !== undefined);

        const can_delete_message = message_delete.get_deletability(message);
        if (!can_delete_message) {
            $checkbox.prop("disabled", true);
        }
        if (message_id === starting_message_id) {
            $checkbox.prop("checked", true);
        }
    });
}

export function initiate_multiple_message_deletion(): void {
    const $rows = message_lists.all_current_message_rows();
    const message_ids: number[] = [];

    $rows.each(function () {
        const $row = $(this);
        const $checkbox = $row.find(".multiple_messages_select input");
        const message_id = Number($checkbox.attr("data-message-id"));

        if ($checkbox.is(":checked")) {
            message_ids.push(message_id);
        }
    });

    const data = {
        message_ids: JSON.stringify(message_ids),
    };

    const html_body = render_confirm_multiple_message_delete({
        selected_message_count: message_ids.length,
    });
    function do_delete_multiple_messages(): void {
        void channel.post({
            url: "/json/messages/delete_multiple",
            data,
            success() {
                dialog_widget.hide_dialog_spinner();
                dialog_widget.close();
            },
            error(xhr) {
                dialog_widget.hide_dialog_spinner();
                ui_report.error(
                    $t_html({defaultMessage: "Error deleting messages"}),
                    xhr,
                    $("#dialog_error"),
                );
            },
        });
    }

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Delete messages"}),
        html_body,
        id: "confirm_multiple_message_delete_modal",
        close_on_submit: false,
        on_click: do_delete_multiple_messages,
        loading_spinner: true,
        on_hide() {
            message_lists.current?.rerender_view();
        },
    });
}
