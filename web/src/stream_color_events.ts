import {$} from "jquery";

import * as compose_recipient from "./compose_recipient.ts";
import * as inbox_util from "./inbox_util.ts";
import * as message_lists from "./message_lists.ts";
import * as message_view_header from "./message_view_header.ts";
import * as overlays from "./overlays.ts";
import * as stream_color from "./stream_color.ts";
import type {StreamSubscription} from "./sub_store.ts";

function update_table_message_recipient_stream_color(
    table: JQuery,
    stream_id: number,
    recipient_bar_color: string,
): void {
    table
        .find(
            `.message_header_stream[data-stream-id='${CSS.escape(stream_id.toString())}'] .message-header-contents`,
        )
        .css({background: recipient_bar_color});
}

function update_stream_privacy_color(id: string, color: string): void {
    $(`.stream-privacy-original-color-${CSS.escape(id)}`).css("color", color);
    color = stream_color.get_stream_privacy_icon_color(color);
    // `modified-color` is only used in recipient bars.
    $(`.stream-privacy-modified-color-${CSS.escape(id)}`).css("color", color);
}

function update_message_recipient_color(stream_id: number, color: string): void {
    const recipient_color = stream_color.get_recipient_bar_color(color);
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        update_table_message_recipient_stream_color(
            msg_list.view.$list,
            stream_id,
            recipient_color,
        );
    }

    // Update color for drafts if open.
    if (overlays.drafts_open()) {
        update_table_message_recipient_stream_color(
            $(".drafts-container"),
            stream_id,
            recipient_color,
        );
    }

    if (inbox_util.is_visible()) {
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
    $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(stream_id)}'] .stream-settings-color-preview`,
    ).css("background-color", color);
    $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            stream_id,
        )}'] .large-icon`,
    ).css("color", color);

    update_message_recipient_color(sub.stream_id, color);
    update_stream_privacy_color(stream_id, color);
    message_view_header.colorize_message_view_header();
    compose_recipient.adjust_compose_channel_privacy_icon_color();
}
