"use strict";

const _ = require("lodash");

const util = require("./util");
// See docs/subsystems/typing-indicators.md for details on typing indicators.

const typist_dct = new Map();
const inbound_timer_dict = new Map();

function to_int(s) {
    return Number.parseInt(s, 10);
}

function get_key(group) {
    const ids = util.sorted_ids(group);
    return ids.join(",");
}

exports.add_typist = function (group, typist) {
    const key = get_key(group);
    const current = typist_dct.get(key) || [];
    typist = to_int(typist);
    if (!current.includes(typist)) {
        current.push(typist);
    }
    typist_dct.set(key, util.sorted_ids(current));
};

exports.remove_typist = function (group, typist) {
    const key = get_key(group);
    let current = typist_dct.get(key) || [];

    typist = to_int(typist);
    if (!current.includes(typist)) {
        return false;
    }

    current = current.filter((user_id) => to_int(user_id) !== to_int(typist));

    typist_dct.set(key, current);
    return true;
};

exports.get_group_typists = function (group) {
    const key = get_key(group);
    return typist_dct.get(key) || [];
};

exports.get_all_typists = function () {
    let typists = [].concat(...Array.from(typist_dct.values()));
    typists = util.sorted_ids(typists);
    typists = _.sortedUniq(typists);
    return typists;
};

// The next functions aren't pure data, but it is easy
// enough to mock the setTimeout/clearTimeout functions.
exports.clear_inbound_timer = function (group) {
    const key = get_key(group);
    const timer = inbound_timer_dict.get(key);
    if (timer) {
        clearTimeout(timer);
        inbound_timer_dict.set(key, undefined);
    }
};

exports.kickstart_inbound_timer = function (group, delay, callback) {
    const key = get_key(group);
    exports.clear_inbound_timer(group);
    const timer = setTimeout(callback, delay);
    inbound_timer_dict.set(key, timer);
};

window.typing_data = exports;
