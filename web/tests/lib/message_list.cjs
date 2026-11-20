"use strict";

const {zrequire} = require("./namespace.cjs");

exports.make_message_list = (filter_terms, opts = {}) => {
    const {Filter} = zrequire("filter");
    const {MessageList} = zrequire("message_list");
    const {MessageListData} = zrequire("message_list_data");

    const filter = new Filter(filter_terms);
    const default_message_list = new MessageList({
        data: new MessageListData({
            filter,
        }),
        is_node_test: true,
    });
    default_message_list.data.participants.humans = new Set(opts.visible_participants);
    return default_message_list;
};
