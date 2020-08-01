"use strict";

const _ = require("lodash");

const render_pm_list_item = require("../templates/pm_list_item.hbs");

exports.keyed_pm_li = (convo) => {
    const render = () => render_pm_list_item(convo);

    const eq = (other) => _.isEqual(convo, other.convo);

    const key = convo.user_ids_string;

    return {
        key,
        render,
        convo,
        eq,
    };
};

exports.pm_ul = (convos) => {
    const attrs = [
        ["class", "expanded_private_messages"],
        ["data-name", "private"],
    ];
    return vdom.ul({
        attrs,
        keyed_nodes: convos.map(exports.keyed_pm_li),
    });
};

window.pm_list_dom = exports;
