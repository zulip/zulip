import * as date_fns from "date-fns";
import $ from "jquery";

import render_scheduled_message from "../templates/scheduled_message.hbs";
import render_scheduled_messages_overlay from "../templates/scheduled_messages_overlay.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as loading from "./loading";
import * as overlays from "./overlays";
import * as people from "./people";
import * as scheduled_messages from "./scheduled_messages";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";

function hide_loading_indicator() {
    loading.destroy_indicator($("#scheduled_messages_overlay .loading-indicator"));
    $(".scheduled-messages-loading").hide();
}

function format(scheduled_messages) {
    const formatted_msgs = [];
    for (const msg of scheduled_messages) {
        const msg_render_context = {...msg};
        if (msg.type === "stream") {
            msg_render_context.is_stream = true;
            msg_render_context.stream_id = msg.to;
            msg_render_context.stream_name = stream_data.maybe_get_stream_name(
                msg_render_context.stream_id,
            );
            const color = stream_data.get_color(msg_render_context.stream_name);
            msg_render_context.recipient_bar_color = stream_color.get_recipient_bar_color(color);
            msg_render_context.stream_privacy_icon_color =
                stream_color.get_stream_privacy_icon_color(color);
        } else {
            msg_render_context.is_stream = false;
            msg_render_context.recipients = people.get_recipients(msg.to.join(","));
        }
        const time = new Date(msg.scheduled_delivery_timestamp * 1000);
        msg_render_context.full_date_time = timerender.get_full_datetime(time);
        msg_render_context.formatted_send_at_time = date_fns.format(time, "MMM d yyyy h:mm a");
        formatted_msgs.push(msg_render_context);
    }
    return formatted_msgs;
}

export function launch() {
    $("#scheduled_messages_overlay_container").empty();
    $("#scheduled_messages_overlay_container").append(render_scheduled_messages_overlay());
    overlays.open_overlay({
        name: "scheduled",
        $overlay: $("#scheduled_messages_overlay"),
        on_close() {
            browser_history.exit_overlay();
        },
    });
    loading.make_indicator($("#scheduled_messages_overlay .loading-indicator"), {
        abs_positioned: true,
    });

    channel.get({
        url: "/json/scheduled_messages",
        success(data) {
            hide_loading_indicator();
            if (data.scheduled_messages.length === 0) {
                $(".no-overlay-messages").show();
            } else {
                // Saving formatted data is helpful when user is trying to edit a scheduled message.
                scheduled_messages.override_scheduled_messages_data(
                    format(data.scheduled_messages),
                );
                const rendered_list = render_scheduled_message({
                    scheduled_messages_data: scheduled_messages.scheduled_messages_data,
                });
                const $messages_list = $("#scheduled_messages_overlay .overlay-messages-list");
                $messages_list.append(rendered_list);
            }
        },
        error(xhr) {
            hide_loading_indicator();
            blueslip.error(xhr);
        },
    });
}

export function initialize() {
    $("body").on("click", ".scheduled-message-row .restore-overlay-message", (e) => {
        let scheduled_msg_id = $(e.currentTarget)
            .closest(".scheduled-message-row")
            .attr("data-message-id");
        scheduled_msg_id = Number.parseInt(scheduled_msg_id, 10);
        scheduled_messages.edit_scheduled_message(scheduled_msg_id);

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".scheduled-message-row .delete-overlay-message", (e) => {
        const scheduled_msg_id = $(e.currentTarget)
            .closest(".scheduled-message-row")
            .attr("data-message-id");
        scheduled_messages.delete_scheduled_message(scheduled_msg_id);

        e.stopPropagation();
        e.preventDefault();
    });
}
