import render_confirm_unstar_all_messages from "../templates/confirm_dialog/confirm_unstar_all_messages.hbs";
import render_confirm_unstar_all_messages_in_topic from "../templates/confirm_dialog/confirm_unstar_all_messages_in_topic.hbs";

import * as confirm_dialog from "./confirm_dialog";
import {$t_html} from "./i18n";
import * as message_flags from "./message_flags";
import * as stream_data from "./stream_data";

export function confirm_unstar_all_messages() {
    const html_body = render_confirm_unstar_all_messages();

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Unstar all messages"}),
        html_body,
        on_click: message_flags.unstar_all_messages,
    });
}

export function confirm_unstar_all_messages_in_topic(stream_id, topic) {
    function on_click() {
        message_flags.unstar_all_messages_in_topic(stream_id, topic);
    }

    const stream_name = stream_data.maybe_get_stream_name(stream_id);
    if (stream_name === undefined) {
        return;
    }

    const html_body = render_confirm_unstar_all_messages_in_topic({
        stream_name,
        topic,
    });

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Unstar messages in topic"}),
        html_body,
        on_click,
    });
}
