"use strict";

const _ = require("lodash");

const people = require("./people");

const huddle_timestamps = new Map();

exports.process_loaded_messages = function (messages) {
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

exports.get_huddles = function () {
    let huddles = Array.from(huddle_timestamps.keys());
    huddles = _.sortBy(huddles, (huddle) => huddle_timestamps.get(huddle));
    return huddles.reverse();
};

window.huddle_data = exports;
