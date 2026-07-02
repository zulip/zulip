import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as channel from "./channel.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";

const messages_response_schema = z.object({
    messages: z.array(
        z.object({
            id: z.number(),
        }),
    ),
});

export function update_dm_last_message_id(
    user_ids_string: string,
    update_dom_on_success: () => void,
): void {
    // After a deletion locally empties a DM conversation, ask the server
    // whether any messages remain and re-add it to the sidebar if so.
    // Mirrors stream_topic_history_util.update_topic_last_message_id.
    const user_ids = people.user_ids_string_to_ids_array(user_ids_string);
    void channel.get({
        url: "/json/messages",
        data: {
            narrow: JSON.stringify([{operator: "dm", operand: user_ids}]),
            anchor: "newest",
            num_before: 1,
            num_after: 0,
        },
        success(raw_data) {
            const {messages} = messages_response_schema.parse(raw_data);
            if (messages.length !== 1) {
                // Still empty; leave it removed.
                return;
            }

            const last_message = messages[0];
            assert(last_message !== undefined);
            pm_conversations.recent.insert(user_ids, last_message.id);
            update_dom_on_success();
        },
        error() {
            // Ideally we would retry since we should always be able to get a
            // success response from the server for this request, but for now
            // we just ignore the error.
        },
    });
}
