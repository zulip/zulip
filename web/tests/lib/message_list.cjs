"use strict";

const {zrequire} = require("./namespace.cjs");

const {Filter} = zrequire("filter");
const {MessageList} = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");

exports.make_message_list = (filter_terms, opts = {}) => {
    const filter = new Filter(filter_terms);
    const default_message_list = new MessageList({
        data: new MessageListData({
            filter,
        }),
        is_node_test: true,
    });
    default_message_list.data.participants.humans = new Set(opts.visible_participants ?? []);
    return default_message_list;
};
