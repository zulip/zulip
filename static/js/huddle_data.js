import _ from "lodash";

import * as people from "./people";

const huddle_timestamps = new Map();

export function clear_for_testing() {
    huddle_timestamps.clear();
}

export function process_loaded_messages(messages) {
    for (const message of messages) {
        const huddle_string = people.huddle_string(message);

        if (huddle_string) {
            const old_timestamp = huddle_timestamps.get(huddle_string);

            if (!old_timestamp || old_timestamp < message.timestamp) {
                huddle_timestamps.set(huddle_string, message.timestamp);
            }
        }
    }
}

export function get_huddles() {
    let huddles = Array.from(huddle_timestamps.keys());
    huddles = _.sortBy(huddles, (huddle) => huddle_timestamps.get(huddle));
    return huddles.reverse();
}
