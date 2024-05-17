import {z} from "zod";

import * as channel from "./channel";
import * as stream_topic_history from "./stream_topic_history";

const stream_topic_history_response_schema = z.object({
    topics: z.array(
        z.object({
            name: z.string(),
            max_id: z.number(),
        }),
    ),
});

export function get_server_history(stream_id: number, on_success: () => void): void {
    if (stream_topic_history.has_history_for(stream_id)) {
        on_success();
        return;
    }
    if (stream_topic_history.is_request_pending_for(stream_id)) {
        return;
    }

    stream_topic_history.add_request_pending_for(stream_id);
    const url = "/json/users/me/" + stream_id + "/topics";

    void channel.get({
        url,
        data: {},
        success(data) {
            const clean_data = stream_topic_history_response_schema.parse(data);
            const server_history = clean_data.topics;
            stream_topic_history.add_history(stream_id, server_history);
            stream_topic_history.remove_request_pending_for(stream_id);
            on_success();
        },
        error() {
            stream_topic_history.remove_request_pending_for(stream_id);
        },
    });
}
