import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import {page_params} from "./page_params";

function truncate_precision(float) {
    return Number.parseFloat(float.toFixed(3));
}

export const get_next_id_float = (function () {
    const already_used = new Set();

    return function () {
        const local_id_increment = 0.01;
        let latest = page_params.max_message_id;
        if (all_messages_data.last() !== undefined) {
            latest = all_messages_data.last().id;
        }
        latest = Math.max(0, latest);
        const local_id_float = truncate_precision(latest + local_id_increment);

        if (already_used.has(local_id_float)) {
            // If our id is already used, it is probably an edge case like we had
            // to abort a very recent message.
            blueslip.warn("We don't reuse ids for local echo.");
            return undefined;
        }

        if (local_id_float % 1 > local_id_increment * 5) {
            blueslip.warn("Turning off local echo for this message to let host catch up");
            return undefined;
        }

        if (local_id_float % 1 === 0) {
            // The logic to stop at 0.05 should prevent us from ever wrapping around
            // to the next integer.
            blueslip.error("Programming error");
            return undefined;
        }

        already_used.add(local_id_float);

        return local_id_float;
    };
})();
