import $ from "jquery";
import * as z from "zod/mini";

import render_topic_summary from "../templates/topic_summary.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {Filter} from "./filter.ts";
import {$t} from "./i18n.ts";
import * as message_fetch from "./message_fetch.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import * as util from "./util.ts";

export function get_narrow_summary(channel_id: number, topic_name: string): void {
    const filter = new Filter([
        {operator: "channel", operand: `${channel_id}`},
        {operator: "topic", operand: topic_name},
    ]);
    const data = {narrow: message_fetch.get_narrow_for_message_fetch(filter)};
    const display_topic_name = util.get_final_topic_display_name(topic_name);
    const unread_topic_params = {
        html_submit_button: $t({defaultMessage: "Mark topic as read"}),
        html_exit_button: $t({defaultMessage: "Close"}),
        on_click() {
            unread_ops.mark_topic_as_read(channel_id, topic_name);
        },
        single_footer_button: false,
    };

    let params = {
        html_submit_button: $t({defaultMessage: "Close"}),
        on_click() {
            // Just close the modal, there is nothing else to do.
        },
        single_footer_button: true,
    };
    if (unread.topic_has_any_unread(channel_id, topic_name)) {
        params = {
            ...params,
            ...unread_topic_params,
        };
    }
    dialog_widget.launch({
        text_heading: display_topic_name,
        html_body: "",
        close_on_submit: true,
        id: "topic-summary-modal",
        footer_minor_text: $t({defaultMessage: "AI summaries may have errors."}),
        ...params,
        post_render() {
            const close_on_success = false;
            dialog_widget.submit_api_request(
                channel.get,
                "/json/messages/summary",
                data,
                {
                    success_continuation(response_data) {
                        const data = z.object({summary: z.string()}).parse(response_data);
                        const summary_markdown = data.summary;
                        const summary_html = render_topic_summary({
                            summary_markdown,
                        });
                        $("#topic-summary-modal .modal__content").addClass("rendered_markdown");
                        $("#topic-summary-modal .modal__content").html(summary_html);
                        rendered_markdown.update_elements(
                            $("#topic-summary-modal .modal__content"),
                        );
                    },
                },
                close_on_success,
            );
        },
    });
}
