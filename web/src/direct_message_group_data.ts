import _ from "lodash";

import type {Message} from "./message_store.ts";
import * as people from "./people.ts";

const direct_message_group_timestamps = new Map<string, number>();

export function clear_for_testing(): void {
    direct_message_group_timestamps.clear();
}

export function process_loaded_messages(messages: Message[]): void {
    for (const message of messages) {
        const direct_message_group = people.direct_message_group_string(message);

        if (direct_message_group) {
            const old_timestamp = direct_message_group_timestamps.get(direct_message_group);

            if (!old_timestamp || old_timestamp < message.timestamp) {
                direct_message_group_timestamps.set(direct_message_group, message.timestamp);
            }
        }
    }
}

export function get_direct_message_groups(): string[] {
    let direct_message_groups = [...direct_message_group_timestamps.keys()];
    direct_message_groups = _.sortBy(direct_message_groups, (direct_message_group) =>
        direct_message_group_timestamps.get(direct_message_group),
    );
    return direct_message_groups.reverse();
}
