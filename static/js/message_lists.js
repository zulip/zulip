import {Filter} from "./filter";
import * as message_list from "./message_list";

export let home;
export let current;

export function set_current(msg_list) {
    current = msg_list;
}

export function initialize() {
    home = new message_list.MessageList({
        table_name: "zhome",
        filter: new Filter([{operator: "in", operand: "home"}]),
        excludes_muted_topics: true,
    });
    current = home;
}
