import $ from "jquery";
import {z} from "zod";

import render_topic_summary from "../templates/topic_summary.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {Filter} from "./filter.ts";
import {$t} from "./i18n.ts";
import * as message_fetch from "./message_fetch.ts";
import * as stream_data from "./stream_data.ts";
import * as util from "./util.ts";

export function get_narrow_summary(channel_id: number, topic_name: string): void {
    const filter = new Filter([
        {operator: "channel", operand: `${channel_id}`},
        {operator: "topic", operand: topic_name},
    ]);
    const data = {narrow: message_fetch.get_narrow_for_message_fetch(filter)};
    const channel_name = stream_data.get_stream_name_from_id(channel_id);
    const display_topic_name = util.get_final_topic_display_name(topic_name);
    dialog_widget.launch({
        html_heading: $t(
            {defaultMessage: "Summary of #${channel_name} > ${topic_name}:"},
            {channel_name, topic_name: display_topic_name},
        ),
        html_body: "",
        html_submit_button: "Close",
        close_on_submit: true,
        on_click() {
            // Just close the modal, there is nothing else to do.
        },
        id: "topic-summary-modal",
        single_footer_button: true,
        post_render() {
            const close_on_success = false;
            dialog_widget.submit_api_request(
                channel.get,
                "/json/messages/summary",
                data,
                {
                    success_continuation(response_data) {
                        const data = z.object({summary: z.string()}).parse(response_data);
                        const message = data.summary;
                        $("#topic-summary-modal .modal__content").html(
                            render_topic_summary({
                                message,
                            }),
                        );
                    },
                },
                close_on_success,
            );
        },
    });
}
