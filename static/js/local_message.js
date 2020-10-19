"use strict";

const XDate = require("xdate");

function truncate_precision(float) {
    return Number.parseFloat(float.toFixed(3));
}

exports.now = function () {
    const timestamp = new XDate().getTime() / 1000;

    return timestamp;
};

exports.insert_message = function (message) {
    // It is a little bit funny to go through the message_events
    // codepath, but it's sort of the idea behind local echo that
    // we are simulating server events before they actually arrive.
    message_events.insert_new_messages([message], true);
};

exports.get_next_id_float = (function () {
    const already_used = new Set();

    return function () {
        const local_id_increment = 0.01;
        let latest = page_params.max_message_id;
        if (typeof message_list.all !== "undefined" && message_list.all.last() !== undefined) {
            latest = message_list.all.last().id;
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

window.local_message = exports;
