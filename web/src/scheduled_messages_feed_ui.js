import $ from "jquery";

import render_scheduled_messages_indicator from "../templates/scheduled_messages_indicator.hbs";

import * as narrow_state from "./narrow_state";
import * as scheduled_messages from "./scheduled_messages";
import * as util from "./util";

function get_scheduled_messages_matching_narrow() {
    const scheduled_messages_list = Object.values(scheduled_messages.scheduled_messages_data);
    const filter = narrow_state.filter();
    const is_conversation_view = filter === undefined ? false : filter.is_conversation_view();
    const current_view_type = narrow_state.narrowed_to_pms() ? "private" : "stream";

    if (!is_conversation_view) {
        return false;
    }

    const matching_scheduled_messages = scheduled_messages_list.filter((scheduled_message) => {
        // One could imagine excluding scheduled messages that failed
        // to send, but structurally, we want to raise awareness of
        // them -- we expect users to cancel/clear/reschedule those if
        // aware of them.

        if (current_view_type !== scheduled_message.type) {
            return false;
        }

        if (scheduled_message.type === "private") {
            // Both of these will be the user IDs for all participants including the
            // current user sorted in ascending order.
            if (scheduled_message.to.toString() === narrow_state.pm_ids_string()) {
                return true;
            }
        } else if (scheduled_message.type === "stream") {
            if (narrow_state.stream_sub() === undefined) {
                return false;
            }
            const narrow_dict = {
                stream_id: narrow_state.stream_sub().stream_id,
                topic: narrow_state.topic(),
            };
            const scheduled_message_dict = {
                stream_id: scheduled_message.to,
                topic: scheduled_message.topic,
            };
            if (util.same_stream_and_topic(narrow_dict, scheduled_message_dict)) {
                return true;
            }
        }
        return false;
    });
    return matching_scheduled_messages;
}

export function update_schedule_message_indicator() {
    $("#scheduled_message_indicator").empty();
    const matching_scheduled_messages = get_scheduled_messages_matching_narrow();
    const scheduled_message_count = matching_scheduled_messages.length;
    if (scheduled_message_count > 0) {
        $("#scheduled_message_indicator").html(
            render_scheduled_messages_indicator({
                scheduled_message_count,
            }),
        );
    }
}
