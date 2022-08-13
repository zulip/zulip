import _ from "lodash";

import render_report_message from "../templates/report_message.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";

export function msgreport_alert(msg) {
    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Alert"}),
        html_body: _.escape(msg),
        html_submit_button: $t_html({defaultMessage: "Ok"}),
        on_click: () => {},
        close_on_submit: true,
        focus_submit_on_open: true,
        single_footer_button: true,
    });
}

export function show_report_dialog(message, afterfunc) {
    const $row = message_lists.current.get_row(message.id);
    if (!$row) {
        return;
    }

    // in case this message isn't selected (which happens)
    message_lists.current.select_id(message.id, {then_scroll: true});
    const $target = $row.find(".messagebox-content");
    // compute the top of the report dialog box
    const scrollDest = message_viewport.$message_pane.scrollTop() + $target.safeOuterHeight() - 40;
    const width = $row.safeOuterWidth() - 54;

    // add the report dialog HTML:
    //  - append() is used to absolutely minimize the DOM overhead of this rarely used feature,
    //    i.e. we don't want *any* extra per-message DOM elements for msgs that aren't reported.
    //  - remove() called in case the user attempts to call report multiple times.
    const html = render_report_message();
    $target.find(".report_message-box").remove();
    $target.append(html);
    $target.find(".report_message-box").css("width", width + "px");

    // nice little animation to gently open the dialog box and then scroll down to it,
    // drawing the user's eyes to the reporting form.  note: for uncondensed long messages,
    // this initial animation (N msec) will happen off-screen, which is fine in practice.
    const $report_message = $row.find(".report_message-box");
    $report_message.slideDown(600, () => {
        message_viewport.$message_pane.animate(
            {scrollTop: scrollDest},
            600,
            afterfunc(message.id, $report_message),
        );
    });
}

export function report_message(message, $report_message, reason, explanation) {
    channel.post({
        url: "/json/messages/" + message.id + "/report",
        data: {
            reason,
            explanation,
        },
        success() {
            $report_message.html(
                $t({
                    defaultMessage:
                        "Thanks! Submitted to the organization's moderation team to review.",
                }),
            );
        },
        error(e) {
            msgreport_alert(
                $t({
                    defaultMessage:
                        "Oops! Failure reporting message - try again, or notify your administrator.\noriginal error: ",
                }) + e.responseJSON.msg,
            );
        },
    });
}
