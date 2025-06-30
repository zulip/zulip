import $ from "jquery";

import render_scheduled_messages_indicator from "../templates/scheduled_messages_indicator.hbs";

import * as narrow_state from "./narrow_state.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import type {ScheduledMessage} from "./scheduled_messages.ts";
import * as util from "./util.ts";

function get_scheduled_messages_matching_narrow(): ScheduledMessage[] {
    const scheduled_messages_list = scheduled_messages.get_all_scheduled_messages();
    const filter = narrow_state.filter();
    const is_conversation_view =
        filter === undefined
            ? false
            : filter.is_conversation_view() || filter.is_conversation_view_with_near();
    const current_view_type = narrow_state.narrowed_to_pms() ? "private" : "stream";

    if (!is_conversation_view) {
        return [];
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
            const current_stream_id = narrow_state.stream_id(narrow_state.filter(), true);
            const current_topic = narrow_state.topic();
            if (current_stream_id === undefined || current_topic === undefined) {
                return false;
            }
            const narrow_dict = {
                stream_id: current_stream_id,
                topic: current_topic,
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

export function update_schedule_message_indicator(): void {
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
