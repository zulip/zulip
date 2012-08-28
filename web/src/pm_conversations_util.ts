import * as message_util from "./message_util.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";

export function update_dm_last_message_id(
    user_ids_string: string,
    update_dom_on_success: () => void,
): void {
    // After a deletion locally empties a DM conversation, ask the server
    // whether any messages remain and re-add it to the sidebar if so.
    // Mirrors stream_topic_history_util.update_topic_last_message_id.
    const user_ids = people.user_ids_string_to_ids_array(user_ids_string);
    message_util.get_last_message_id_in_narrow(
        [{operator: "dm", operand: user_ids}],
        (last_message_id) => {
            pm_conversations.recent.insert(user_ids, last_message_id);
            update_dom_on_success();
        },
    );
}
