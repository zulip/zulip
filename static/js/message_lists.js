import {Filter} from "./filter";
import * as home_message_list from "./home_message_list";
import * as recent_topics_util from "./recent_topics_util";

export let home;
export let current;

export function set_current(msg_list) {
    current = msg_list;
    debugger;
    home.set_current_message_list(home === current)
}

export function all_rendered_message_lists() {
    const rendered_message_lists = [home];
    if (current !== home && !recent_topics_util.is_visible()) {
        rendered_message_lists.push(current);
    }
    return rendered_message_lists;
}

export function initialize() {
    home = new home_message_list.HomeMessageList({
        filter: new Filter([{operator: "in", operand: "home"}]),
        excludes_muted_topics: true,
    });
    current = home;
}
