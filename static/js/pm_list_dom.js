import _ from "lodash";

import render_pm_list_item from "../templates/pm_list_item.hbs";

import * as vdom from "./vdom";

export function keyed_pm_li(conversation) {
    const render = () => render_pm_list_item(conversation);

    const eq = (other) => _.isEqual(conversation, other.conversation);

    const key = conversation.user_ids_string;

    return {
        key,
        render,
        conversation,
        eq,
    };
}

export function pm_ul(conversations) {
    const attrs = [
        ["class", "expanded_private_messages"],
        ["data-name", "private"],
    ];
    return vdom.ul({
        attrs,
        keyed_nodes: conversations.map((conversation) => keyed_pm_li(conversation)),
    });
}
