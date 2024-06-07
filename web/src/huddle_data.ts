import _ from "lodash";

import type {Message} from "./message_store";
import * as people from "./people";

const huddle_timestamps = new Map<string, number>();

export const clear_for_testing = (): void => {
    huddle_timestamps.clear();
};

export const process_loaded_messages = (messages: Message[]): void => {
    for (const message of messages) {
        const huddle_string = people.huddle_string(message);

        if (huddle_string) {
            const old_timestamp = huddle_timestamps.get(huddle_string);

            if (!old_timestamp || old_timestamp < message.timestamp) {
                huddle_timestamps.set(huddle_string, message.timestamp);
            }
        }
    }
};

export const get_huddles = (): string[] => {
    let huddles = [...huddle_timestamps.keys()];
    huddles = _.sortBy(huddles, (huddle) => huddle_timestamps.get(huddle));
    return huddles.reverse();
};
