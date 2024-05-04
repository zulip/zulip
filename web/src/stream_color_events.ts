import $ from "jquery";

import * as inbox_util from "./inbox_util";
import * as message_lists from "./message_lists";
import * as message_view_header from "./message_view_header";
import * as overlays from "./overlays";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";

function update_table_message_recipient_stream_color(
    table: JQuery,
    stream_name: string,
    recipient_bar_color: string,
): void {
    const $stream_labels = table.find(".stream_label");
    for (const label of $stream_labels) {
        const $label = $(label);
        if ($label.text().trim() === stream_name) {
            $label
                .closest(".message_header_stream .message-header-contents")
                .css({background: recipient_bar_color});
        }
    }
}

function update_stream_privacy_color(id: string, color: string): void {
    $(`.stream-privacy-original-color-${CSS.escape(id)}`).css("color", color);
    color = stream_color.get_stream_privacy_icon_color(color);
    // `modified-color` is only used in recipient bars.
    $(`.stream-privacy-modified-color-${CSS.escape(id)}`).css("color", color);
}

function update_message_recipient_color(stream_name: string, color: string): void {
    const recipient_color = stream_color.get_recipient_bar_color(color);
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        update_table_message_recipient_stream_color(
            msg_list.view.$list,
            stream_name,
            recipient_color,
        );
    }

    // Update color for drafts if open.
    if (overlays.drafts_open()) {
        update_table_message_recipient_stream_color(
            $(".drafts-container"),
            stream_name,
            recipient_color,
        );
    }

    if (inbox_util.is_visible()) {
        const stream_id = stream_data.get_stream_id(stream_name);
        $(`#inbox-stream-header-${stream_id}`).css("background", recipient_color);
    }
}

export function update_stream_color(sub: StreamSubscription, color: string): void {
    sub.color = color;
    const stream_id = sub.stream_id.toString();
    // The swatch in the subscription row header.
    $(`.stream-row[data-stream-id='${CSS.escape(stream_id)}'] .icon`).css(
        "background-color",
        color,
    );
    // The swatch in the color picker.
    stream_color.set_colorpicker_color(
        $(
            `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
                stream_id,
            )}'] .colorpicker`,
        ),
        color,
    );
    $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            stream_id,
        )}'] .large-icon`,
    ).css("color", color);

    update_message_recipient_color(sub.name, color);
    update_stream_privacy_color(stream_id, color);
    message_view_header.colorize_message_view_header();
}
