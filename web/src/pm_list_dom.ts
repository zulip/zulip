import _ from "lodash";

import render_more_private_conversations from "../templates/more_pms.hbs";
import render_pm_list_item from "../templates/pm_list_item.hbs";

import * as vdom from "./vdom";

// TODO/typescript: Move this to pm_list_data
type PMListConversation = {
    user_ids_string: string;
};

type PMNode = vdom.Node & {
    conversation: PMListConversation;
};

export function keyed_pm_li(conversation: PMListConversation): PMNode {
    const render = (): string => render_pm_list_item(conversation);

    const eq = (other: PMNode): boolean => _.isEqual(conversation, other.conversation);

    const key = conversation.user_ids_string;

    return {
        key,
        render,
        conversation,
        eq,
    };
}

type MorePrivateConversationsNode = vdom.Node & {
    more_items: boolean;
    more_conversations_unread_count: number;
};

export function more_private_conversations_li(
    more_conversations_unread_count: number,
): MorePrivateConversationsNode {
    const render = (): string =>
        render_more_private_conversations({more_conversations_unread_count});

    // Used in vdom.js to check if an element has changed and needs to
    // be updated in the DOM.
    const eq = (other: MorePrivateConversationsNode): boolean =>
        other.more_items &&
        more_conversations_unread_count === other.more_conversations_unread_count;

    // This special key must be impossible as a user_ids_string.
    const key = "more_private_conversations";

    return {
        key,
        more_items: true,
        more_conversations_unread_count,
        render,
        eq,
    };
}

export function pm_ul(nodes: vdom.Node[]): vdom.Tag {
    const attrs: [string, string][] = [
        ["class", "dm-list"],
        ["data-name", "private"],
    ];
    return vdom.ul({
        attrs,
        keyed_nodes: nodes,
    });
}
