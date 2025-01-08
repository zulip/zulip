import assert from "minimalistic-assert";
import {z} from "zod";

import * as channel from "./channel.ts";
import * as stream_topic_history from "./stream_topic_history.ts";

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
        success(raw_data) {
            const data = stream_topic_history_response_schema.parse(raw_data);
            const server_history = data.topics;
            stream_topic_history.add_history(stream_id, server_history);
            stream_topic_history.remove_request_pending_for(stream_id);
            on_success();
        },
        error() {
            stream_topic_history.remove_request_pending_for(stream_id);
        },
    });
}

export function update_topic_last_message_id(
    stream_id: number,
    topic_name: string,
    update_dom_on_success: () => void,
): void {
    void channel.get({
        url: "/json/messages",
        data: {
            narrow: JSON.stringify([
                {operator: "stream", operand: stream_id},
                {operator: "topic", operand: topic_name},
            ]),
            anchor: "newest",
            num_before: 1,
            num_after: 0,
            allow_empty_topic_name: true,
        },
        success(data) {
            const {messages} = z
                .object({
                    messages: z.array(
                        z.object({
                            id: z.number(),
                        }),
                    ),
                })
                .parse(data);
            if (messages.length !== 1) {
                return;
            }

            const last_message = messages[0];
            assert(last_message !== undefined);
            stream_topic_history.add_history(stream_id, [
                {
                    name: topic_name,
                    max_id: last_message.id,
                },
            ]);
            update_dom_on_success();
        },
        error() {
            // Ideally we would retry since we should always be able to get a success response
            // from the server for this request, but for now we just ignore the error.
        },
    });
}
