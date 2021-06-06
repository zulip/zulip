import * as channel from "./channel";
import * as stream_topic_history from "./stream_topic_history";

export function get_server_history(stream_id, on_success) {
    if (stream_topic_history.has_history_for(stream_id)) {
        on_success();
        return;
    }

    const url = "/json/users/me/" + stream_id + "/topics";

    channel.get({
        url,
        data: {},
        success(data) {
            const server_history = data.topics;
            stream_topic_history.add_history(stream_id, server_history);
            on_success();
        },
    });
}
