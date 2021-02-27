import _ from "lodash";

import render_pm_list_item from "../templates/pm_list_item.hbs";

import * as vdom from "./vdom";

export function keyed_pm_li(convo) {
    const render = () => render_pm_list_item(convo);

    const eq = (other) => _.isEqual(convo, other.convo);

    const key = convo.user_ids_string;

    return {
        key,
        render,
        convo,
        eq,
    };
}

export function pm_ul(convos) {
    const attrs = [
        ["class", "expanded_private_messages"],
        ["data-name", "private"],
    ];
    return vdom.ul({
        attrs,
        keyed_nodes: convos.map((convo) => keyed_pm_li(convo)),
    });
}
